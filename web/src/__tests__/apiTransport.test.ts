/**
 * api.ts 请求传输逻辑测试：重试次数、超时中止、错误格式化。
 *
 * 通过 stub 全局 fetch 黑盒驱动公开 api 方法，验证：
 * - 幂等 GET 在 5xx/网络错误下按 RETRY_COUNT 重试
 * - 非幂等 POST/PUT/DELETE 不重试
 * - 超时后 abort signal 生效并抛错
 * - detail 字符串 / 数组 / 缺失时的错误消息映射
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";

function mockResp(status: number, body: unknown, statusText = ""): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("api 重试策略", () => {
  it("GET 幂等请求在 5xx 时按 RETRY_COUNT=2 重试，最终成功", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockResp(500, { detail: "boom" }))
      .mockResolvedValueOnce(mockResp(500, { detail: "boom" }))
      .mockResolvedValueOnce(mockResp(200, [{ id: 1, symbol: "600519" }]));
    vi.stubGlobal("fetch", fetchMock);

    const promise = api.holdings();
    await vi.runAllTimersAsync();
    const result = await promise;

    expect(fetchMock).toHaveBeenCalledTimes(3); // 1 次初始 + 2 次重试
    expect(result).toEqual([{ id: 1, symbol: "600519" }]);
  });

  it("GET 5xx 重试耗尽后抛出最后一次错误", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockResolvedValue(mockResp(503, { detail: "服务不可用" }));
    vi.stubGlobal("fetch", fetchMock);

    const promise = api.holdings();
    // 提前附加处理器，避免 fake timers 推进期间被上报为 unhandled rejection
    promise.catch(() => {});
    await vi.runAllTimersAsync();

    await expect(promise).rejects.toThrow("服务不可用");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("网络错误时 GET 重试并在重试耗尽后抛出该错误", async () => {
    vi.useFakeTimers();
    // 在微任务中 reject，避免 mockRejectedValue 的“创建即拒绝”触发 unhandled rejection 警告
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve().then(() => {
        throw new TypeError("Failed to fetch");
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const promise = api.holdings();
    // 提前附加处理器，避免 fake timers 推进期间被上报为 unhandled rejection
    promise.catch(() => {});
    await vi.runAllTimersAsync();

    await expect(promise).rejects.toThrow("Failed to fetch");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("非幂等 POST 请求 5xx 时不重试", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResp(500, { detail: "server error" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      api.addHolding({ symbol: "600519", name: "贵州茅台", cost_price: 1800, lots: 1 }),
    ).rejects.toThrow("server error");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("非幂等 DELETE 请求 5xx 时不重试", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResp(500, { detail: "server error" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.deleteHolding(42)).rejects.toThrow("server error");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("api 超时中止", () => {
  it("请求挂起超过 30s 时触发 abort 并抛出错误（POST 不重试）", async () => {
    vi.useFakeTimers();
    let capturedSignal: AbortSignal | undefined;
    const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      capturedSignal = init?.signal ?? undefined;
      return new Promise<Response>((_resolve, reject) => {
        capturedSignal?.addEventListener("abort", () =>
          reject(new DOMException("Aborted", "AbortError")),
        );
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const promise = api.addHolding({
      symbol: "600519",
      name: "贵州茅台",
      cost_price: 1800,
      lots: 1,
    });
    // 提前附加处理器，避免 fake timers 推进期间被上报为 unhandled rejection
    promise.catch(() => {});
    await vi.advanceTimersByTimeAsync(30_000);

    await expect(promise).rejects.toThrow("Aborted");
    expect(capturedSignal?.aborted).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("GET 超时后每轮尝试都会重建 abort signal 并最终失败", async () => {
    vi.useFakeTimers();
    const signals: AbortSignal[] = [];
    const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      const signal = init?.signal as AbortSignal;
      signals.push(signal);
      return new Promise<Response>((_resolve, reject) => {
        signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const promise = api.holdings();
    promise.catch(() => {});
    await vi.runAllTimersAsync();

    await expect(promise).rejects.toThrow("Aborted");
    expect(signals).toHaveLength(3);
    expect(signals.every((s) => s.aborted)).toBe(true);
  });
});

describe("api 错误格式化", () => {
  it("detail 为字符串时直接作为错误消息", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResp(400, { detail: "参数错误" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.holdings()).rejects.toThrow("参数错误");
  });

  it("detail 为数组时拼接各条 msg", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockResp(400, { detail: [{ msg: "a" }, { msg: "b" }] }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.holdings()).rejects.toThrow("a; b");
  });

  it("detail 缺失时回退为「请求失败」", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResp(400, {}));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.holdings()).rejects.toThrow("请求失败");
  });

  it("错误响应体非 JSON 时回退 statusText", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: () => Promise.reject(new Error("not json")),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.holdings()).rejects.toThrow("Bad Gateway");
  });
});

describe("api 请求组装", () => {
  it("请求携带 Content-Type: application/json", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResp(200, []));
    vi.stubGlobal("fetch", fetchMock);

    await api.holdings();

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/portfolio/holdings");
  });

  it("POST 请求序列化 JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResp(200, { id: 1 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.addHolding({ symbol: "600519", name: "贵州茅台", cost_price: 1800, lots: 1 });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      symbol: "600519",
      name: "贵州茅台",
      cost_price: 1800,
      lots: 1,
    });
  });
});
