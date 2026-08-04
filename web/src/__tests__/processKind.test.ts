import { describe, expect, it } from "vitest";
import { detectProcessFlow, processTrailLabel } from "../processKind";
import { applyStreamEvent, emptyStreamState } from "../streamEvents";
import { createT } from "../i18n";

const t = createT("zh");

describe("detectProcessFlow", () => {
  it("classifies simple ReAct status-only streams as react", () => {
    let state = emptyStreamState();
    state = applyStreamEvent(state, {
      type: "status",
      message_key: "status.react.thinking",
      message: "正在思考… (第1步)",
      message_params: { step: 1 },
    });
    expect(detectProcessFlow(state)).toBe("react");
    expect(processTrailLabel(state, true, t)).toBe("思考过程");
  });

  it("classifies plan-execute status lines as plan", () => {
    let state = emptyStreamState();
    state = applyStreamEvent(state, {
      type: "status",
      message_key: "status.plan.step",
      message: "执行步骤 1/3: 获取行情",
      message_params: { step_id: 1, total: 3, desc: "获取行情" },
    });
    expect(detectProcessFlow(state)).toBe("plan");
    expect(processTrailLabel(state, false, t)).toBe("规划规程");
  });

  it("classifies stock research skill with dimension title", () => {
    let state = emptyStreamState();
    state = applyStreamEvent(state, {
      type: "skill_start",
      skill_id: "skill_stock_research",
      skill_run_id: "run-1",
      label: "个股四维投研",
    });
    expect(detectProcessFlow(state)).toBe("stock_research");
    expect(processTrailLabel(state, true, t)).toBe("基本面/技术面/情绪面/筹码面 四维投研");
  });

  it("classifies bull bear debate skill", () => {
    let state = emptyStreamState();
    state = applyStreamEvent(state, {
      type: "skill_start",
      skill_id: "skill_bull_bear_debate",
      skill_run_id: "run-2",
      label: "多空辩论",
    });
    expect(detectProcessFlow(state)).toBe("debate");
    expect(processTrailLabel(state, true, t)).toBe("多空辩论");
  });

  it("classifies dimension agent output as stock research", () => {
    let state = emptyStreamState();
    state = applyStreamEvent(state, {
      type: "agent_start",
      agent_id: "fundamental",
      agent_name: "基本面",
      role: "analyst",
    });
    expect(detectProcessFlow(state)).toBe("stock_research");
  });
});
