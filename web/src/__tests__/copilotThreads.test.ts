import { describe, expect, it } from "vitest";
import type { Message } from "../appTypes";
import { autoThreadTitle, createThread, messagesForStorage, truncateThreadTitle } from "../copilotThreads";

describe("copilotThreads", () => {
  it("truncates long titles", () => {
    const long = "分析贵州茅台今天的走势和主要驱动因素以及估值水平";
    expect(truncateThreadTitle(long, 16).length).toBeLessThanOrEqual(16);
  });

  it("auto titles from first query", () => {
    expect(autoThreadTitle("分析宁德时代", "新对话")).toBe("分析宁德时代");
    expect(autoThreadTitle("  ", "新对话")).toBe("新对话");
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
