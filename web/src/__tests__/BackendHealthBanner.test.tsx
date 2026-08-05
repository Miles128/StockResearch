/**
 * BackendHealthBanner 组件行为测试：健康探测状态机。
 *
 * - ok（JSON + status=ok）→ 不渲染
 * - 网络错误 / 超时 → unreachable 提示
 * - 非 JSON / 非 ok 状态码 / 字段缺失 → wrong-service 提示
 * - 用户可关闭提示
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BackendHealthBanner } from "../BackendHealthBanner";

vi.mock("../i18n", () => ({
  useI18n: () => ({ t: (k: string) => k, locale: "zh" }),
}));

afterEach(() => {
  vi.unstubAllGlobals();
});

function healthResponse(opts: {
  ok?: boolean;
  contentType?: string;
  json?: unknown;
  jsonRejects?: boolean;
}): Response {
  const { ok = true, contentType = "application/json", json, jsonRejects = false } = opts;
  return {
    ok,
    headers: { get: () => contentType },
    json: () =>
      jsonRejects
        ? Promise.reject(new Error("not json"))
        : Promise.resolve(json ?? { status: "ok" }),
  } as unknown as Response;
}

describe("BackendHealthBanner", () => {
  it("后端 status=ok 时隐藏提示", async () => {
    const fetchMock = vi.fn().mockResolvedValue(healthResponse({}));
    vi.stubGlobal("fetch", fetchMock);

    render(<BackendHealthBanner />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("网络错误时显示 unreachable 提示", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    render(<BackendHealthBanner />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("health.unreachableTitle");
  });

  it("响应体非 JSON 时显示 wrong-service 提示", async () => {
    const fetchMock = vi.fn().mockResolvedValue(healthResponse({ contentType: "text/html" }));
    vi.stubGlobal("fetch", fetchMock);

    render(<BackendHealthBanner />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("health.wrongServiceTitle");
  });

  it("非 ok 状态码时显示 wrong-service 提示", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(healthResponse({ ok: false, contentType: "application/json" }));
    vi.stubGlobal("fetch", fetchMock);

    render(<BackendHealthBanner />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("health.wrongServiceTitle");
  });

  it("JSON 缺少 status=ok 时显示 wrong-service 提示", async () => {
    const fetchMock = vi.fn().mockResolvedValue(healthResponse({ json: { hello: "world" } }));
    vi.stubGlobal("fetch", fetchMock);

    render(<BackendHealthBanner />);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("health.wrongServiceTitle");
  });

  it("点击关闭按钮后隐藏提示", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    render(<BackendHealthBanner />);

    const alert = await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "close" }));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(alert).toBeTruthy();
  });
});
