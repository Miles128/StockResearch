/** SSE header merge includes data-source BYOK headers. */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../dataSourceSettings", () => ({
  dataSourceRequestHeaders: () => ({ "X-Tushare-Token": "tok-test" }),
}));

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
