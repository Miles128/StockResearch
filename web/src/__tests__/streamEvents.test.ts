import { describe, expect, it } from "vitest";
import {
  applyStreamEvent,
  emptyStreamState,
  finalizeStreamState,
  hasLiveProcessContent,
  hasProcessContent,
} from "../streamEvents";

describe("streamEvents completion state", () => {
  it("drops transient react status after finalize", () => {
    let state = emptyStreamState();
    state = applyStreamEvent(state, {
      type: "status",
      message_key: "status.understanding",
      message: "正在理解您的问题…",
    });
    state = applyStreamEvent(state, {
      type: "status",
      message_key: "status.react.thinking",
      message: "正在思考… (第1步)",
      message_params: { step: 1 },
    });

    expect(hasLiveProcessContent(state)).toBe(true);
    expect(hasProcessContent(state)).toBe(false);

    const done = finalizeStreamState(state, "分析完成");
    expect(done.streamLog).toEqual([]);
    expect(done.streamStatus).toBe("分析完成");
    expect(hasProcessContent(done)).toBe(false);
    expect(hasLiveProcessContent(done)).toBe(true);
  });

  it("keeps substantive agent output after finalize", () => {
    let state = emptyStreamState();
    state = applyStreamEvent(state, {
      type: "agent_start",
      agent_id: "custom_analyst",
      agent_name: "分析师",
      role: "analyst",
    });
    state = applyStreamEvent(state, {
      type: "text_delta",
      stream_id: "custom_analyst",
      agent_id: "custom_analyst",
      delta: "盈利稳健",
    });

    const done = finalizeStreamState(state, "分析完成");
    expect(hasProcessContent(done)).toBe(true);
    expect(done.agentSteps[0]?.content).toContain("盈利稳健");
    expect(done.streamLog).toEqual([]);
  });
});
