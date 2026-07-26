import { describe, expect, it } from "vitest";
import type { Message } from "../appTypes";
import {
  autoThreadTitle,
  createThread,
  messagesForStorage,
  titleFromMessages,
  truncateThreadTitle,
} from "../copilotThreads";

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
});
