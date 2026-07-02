import { describe, expect, it } from "vitest";
import type { Message } from "../appTypes";
import {
  autoThreadTitle,
  createThread,
  messagesForStorage,
  shouldForkCopilotThread,
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

  it("forks thread when topic shifts from stock to market", () => {
    const messages: Message[] = [
      { role: "user", content: "分析贵州茅台" },
      { role: "assistant", content: "..." },
    ];
    const known = [{ symbol: "600519", name: "贵州茅台" }];
    expect(shouldForkCopilotThread(messages, "今天A股大盘走势如何", known)).toBe(true);
    expect(shouldForkCopilotThread(messages, "茅台估值怎么看", known)).toBe(false);
  });

  it("forks thread when switching stocks", () => {
    const messages: Message[] = [{ role: "user", content: "分析600519" }];
    const known = [
      { symbol: "600519", name: "贵州茅台" },
      { symbol: "300750", name: "宁德时代" },
    ];
    expect(shouldForkCopilotThread(messages, "帮我看看300750", known)).toBe(true);
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
