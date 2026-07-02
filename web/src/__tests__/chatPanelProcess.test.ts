import { describe, expect, it } from "vitest";
import { finalizeStreamState, hasProcessContent, emptyStreamState } from "../streamEvents";

describe("streamEvents finalize", () => {
  it("marks stream done and clears live status lines", () => {
    const state = {
      ...emptyStreamState(),
      streamStatus: "分析中…",
      streamLog: ["正在思考…", "获取行情"],
      agentSteps: [{ agent_id: "a1", agent_name: "Research", role: "research", status: "done" as const }],
    };
    const done = finalizeStreamState(state, "分析完成");
    expect(done.streamStatus).toBe("分析完成");
    expect(done.streamLog).not.toContain("正在思考…");
    expect(hasProcessContent(done)).toBe(true);
  });

  it("hasProcessContent is false for empty snapshot", () => {
    expect(hasProcessContent(emptyStreamState())).toBe(false);
  });
});
