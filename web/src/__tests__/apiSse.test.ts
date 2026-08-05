/** SSE header merge includes data-source BYOK headers. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../dataSourceSettings", () => ({
  dataSourceRequestHeaders: () => ({ "X-Tushare-Token": "tok-test" }),
}));

function readerFromChunks(chunks: string[]): {
  reader: {
    read: () => Promise<{ done: boolean; value?: Uint8Array }>;
    cancel: () => Promise<void>;
    releaseLock: () => void;
  };
  cancelMock: ReturnType<typeof vi.fn>;
} {
  const cancelMock = vi.fn().mockResolvedValue(undefined);
  const encoder = new TextEncoder();
  let i = 0;
  return {
    cancelMock,
    reader: {
      read: () => {
        if (i < chunks.length) {
          const value = encoder.encode(chunks[i]);
          i += 1;
          return Promise.resolve({ done: false, value });
        }
        return Promise.resolve({ done: true, value: undefined });
      },
      cancel: cancelMock,
      releaseLock: () => {},
    },
  };
}

function sseResponse(reader: {
  read: () => Promise<{ done: boolean; value?: Uint8Array }>;
  cancel: () => Promise<void>;
  releaseLock: () => void;
}): Response {
  return {
    ok: true,
    body: { getReader: () => reader },
  } as unknown as Response;
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("createJsonSseStream headers", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("merges dataSourceRequestHeaders into fetch", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn().mockResolvedValue({ done: true, value: undefined }),
          cancel: vi.fn().mockResolvedValue(undefined),
          releaseLock: vi.fn(),
        }),
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    const { createJsonSseStream } = await import("../apiSse");
    await createJsonSseStream({
      url: "/api/v1/research/analyze/stream?symbol=600519",
      headers: { "X-LLM-Provider": "mock" },
      extractResult: () => undefined,
    });

    expect(fetchMock).toHaveBeenCalled();
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers["X-Tushare-Token"]).toBe("tok-test");
    expect(headers["X-LLM-Provider"]).toBe("mock");
    expect(headers["Content-Type"]).toBe("application/json");
  });
});

describe("createJsonSseStream 组装", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("逐条解析 data: 事件并触发 onEvent", async () => {
    const { reader } = readerFromChunks([
      'data: {"type":"status","message":"理解中"}\n\n',
      'data: {"type":"agent_start","agent_id":"a1"}\n\n',
    ]);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse(reader)));

    const { createJsonSseStream } = await import("../apiSse");
    const onEvent = vi.fn();
    await createJsonSseStream({
      url: "/api/v1/chat/stream",
      onEvent,
      extractResult: () => undefined,
    });

    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent.mock.calls[0][0]).toEqual({ type: "status", message: "理解中" });
    expect(onEvent.mock.calls[1][0]).toEqual({ type: "agent_start", agent_id: "a1" });
  });

  it("跳过 [DONE] 与非法 JSON 行", async () => {
    const { reader } = readerFromChunks([
      "data: [DONE]\n\n",
      "data: {bad json\n\n",
      'data: {"type":"done","result":{"symbol":"600519"}}\n\n',
      'data: {"type":"ignored"}\n\n',
    ]);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse(reader)));

    const { createJsonSseStream } = await import("../apiSse");
    const onEvent = vi.fn();
    const result = await createJsonSseStream<
      { symbol: string },
      { type: string; result?: { symbol: string } }
    >({
      url: "/api/v1/chat/stream",
      onEvent,
      extractResult: (event) => (event.type === "done" ? event.result : undefined),
    });

    expect(onEvent).toHaveBeenCalledTimes(2); // done + ignored，[DONE] 与坏 JSON 被跳过
    expect(result).toEqual({ symbol: "600519" });
  });

  it("跨 chunk 边界拼接并组装事件", async () => {
    // 事件被拆成两个 chunk：第一行在 chunk1 末尾不完整
    const { reader } = readerFromChunks([
      'data: {"type":"text_delta","de',
      'lta":"你"}\n\ndata: {"type":"text_delta","delta":"好"}\n\n',
    ]);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse(reader)));

    const { createJsonSseStream } = await import("../apiSse");
    const onEvent = vi.fn();
    await createJsonSseStream({
      url: "/api/v1/chat/stream",
      onEvent,
      extractResult: () => undefined,
    });

    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent.mock.calls[0][0]).toEqual({ type: "text_delta", delta: "你" });
    expect(onEvent.mock.calls[1][0]).toEqual({ type: "text_delta", delta: "好" });
  });

  it("非 ok 响应抛出流式请求失败", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 503 } as unknown as Response),
    );

    const { createJsonSseStream } = await import("../apiSse");
    await expect(
      createJsonSseStream({ url: "/api/v1/chat/stream", extractResult: () => undefined }),
    ).rejects.toThrow("流式请求失败");
  });

  it("无响应体时抛出流式请求失败", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, body: null } as unknown as Response),
    );

    const { createJsonSseStream } = await import("../apiSse");
    await expect(
      createJsonSseStream({ url: "/api/v1/chat/stream", extractResult: () => undefined }),
    ).rejects.toThrow("流式请求失败");
  });

  it("读取超时后中止并返回已收集结果", async () => {
    vi.useFakeTimers();
    const cancelMock = vi.fn().mockResolvedValue(undefined);
    const neverEndingReader = {
      read: () => new Promise<{ done: boolean; value?: Uint8Array }>(() => {}),
      cancel: cancelMock,
      releaseLock: () => {},
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse(neverEndingReader)));

    const { createJsonSseStream } = await import("../apiSse");
    const promise = createJsonSseStream({
      url: "/api/v1/chat/stream",
      timeoutMs: 1000,
      extractResult: () => undefined,
    });
    promise.catch(() => {});
    await vi.advanceTimersByTimeAsync(1000);

    await expect(promise).resolves.toBeNull();
    expect(cancelMock).toHaveBeenCalled();
  });

  it("外部 signal 中止时取消 reader", async () => {
    const { reader, cancelMock } = readerFromChunks([
      'data: {"type":"status","message":"理解中"}\n\n',
    ]);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse(reader)));

    const { createJsonSseStream } = await import("../apiSse");
    const controller = new AbortController();
    const promise = createJsonSseStream({
      url: "/api/v1/chat/stream",
      signal: controller.signal,
      extractResult: () => undefined,
    });
    promise.catch(() => {});
    // 等首块读入并挂起后中止
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    controller.abort();

    await expect(promise).resolves.toBeNull();
    expect(cancelMock).toHaveBeenCalled();
  });
});
