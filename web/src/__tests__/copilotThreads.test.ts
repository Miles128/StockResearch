import { afterEach, describe, expect, it, vi } from "vitest";
import type { Message } from "../appTypes";
import {
  autoThreadTitle,
  createThread,
  messagesForStorage,
  saveCopilotThreads,
  titleFromMessages,
  truncateThreadTitle,
} from "../copilotThreads";

// jsdom 29 默认不提供 localStorage；测试用内存实现替代。
function installLocalStorageMock(): Map<string, string> {
  const store = new Map<string, string>();
  const mock: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    key: (i: number) => [...store.keys()][i] ?? null,
    removeItem: (k: string) => {
      store.delete(k);
    },
    setItem: (k: string, v: string) => {
      store.set(k, String(v));
    },
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: mock,
    configurable: true,
    writable: true,
  });
  return store;
}

const store = installLocalStorageMock();

afterEach(() => {
  store.clear();
  vi.restoreAllMocks();
});

describe("copilotThreads", () => {
  it("truncates long titles", () => {
    const long = "分析贵州茅台今天的走势和主要驱动因素以及估值水平";
    expect(truncateThreadTitle(long, 16).length).toBeLessThanOrEqual(16);
  });

  it("auto titles from first query", () => {
    expect(autoThreadTitle("分析宁德时代", "新对话")).toBe("分析宁德时代");
    expect(autoThreadTitle("  ", "新对话")).toBe("新对话");
  });

  it("updates title from latest user message", () => {
    const messages: Message[] = [
      { role: "user", content: "分析茅台" },
      { role: "assistant", content: "..." },
      { role: "user", content: "今天大盘怎么样" },
    ];
    expect(titleFromMessages(messages, "新对话")).toBe("今天大盘怎么样");
  });

  it("keeps topic shifts on the same thread title helper (no auto-fork)", () => {
    // Product rule: only Plus starts a new thread; topic change only updates title.
    const messages: Message[] = [
      { role: "user", content: "分析贵州茅台" },
      { role: "assistant", content: "..." },
      { role: "user", content: "今天A股大盘走势如何" },
    ];
    expect(titleFromMessages(messages, "新对话")).toBe("今天A股大盘走势如何");
  });

  it("strips process from stored messages", () => {
    const stored = messagesForStorage([
      {
        role: "assistant",
        content: "ok",
        process: { streamStatus: "x" } as Message["process"],
      },
    ]);
    expect(stored[0].process).toBeUndefined();
  });

  it("creates thread with id and timestamps", () => {
    const thread = createThread("新对话");
    expect(thread.id).toMatch(/^t_/);
    expect(thread.title).toBe("新对话");
    expect(thread.messages).toEqual([]);
  });

  it("caps messages per thread at 200 (drops oldest)", () => {
    const thread = createThread("长对话");
    const msgs: Message[] = Array.from({ length: 250 }, (_, i) => ({
      role: i % 2 ? "assistant" : "user",
      content: `msg-${i}`,
    }));
    saveCopilotThreads([{ ...thread, messages: msgs }]);
    const saved = JSON.parse(store.get("stockresearch.copilotThreads")!);
    expect(saved[0].messages).toHaveLength(200);
    expect(saved[0].messages[0].content).toBe("msg-50");
    expect(saved[0].messages[199].content).toBe("msg-249");
  });

  it("does not throw when localStorage quota is exceeded", () => {
    const thread = createThread("溢出");
    const setItem = vi.spyOn(globalThis.localStorage, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    expect(() =>
      saveCopilotThreads([{ ...thread, messages: [{ role: "user", content: "hi" }] }]),
    ).not.toThrow();
    setItem.mockRestore();
  });

  it("persists a normal thread to storage", () => {
    const thread = createThread("正常");
    saveCopilotThreads([{ ...thread, messages: [{ role: "user", content: "hi" }] }]);
    const saved = JSON.parse(store.get("stockresearch.copilotThreads")!);
    expect(saved).toHaveLength(1);
    expect(saved[0].title).toBe("正常");
  });
});
