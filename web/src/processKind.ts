import type { SkillStep, SkillStreamSlice, StreamState } from "./streamEvents";
import {
  dimensionDefsForKind,
  detectDimensionSet,
  isDimensionAgent,
  type DimensionKind,
} from "./dimensionStream";
import { isRiskWorkflowAgent } from "./riskWorkflow";

/** Copilot workflow — drives process panel titles. */
export type ProcessFlow =
  | "react"
  | "plan"
  | "stock_research"
  | "market_research"
  | "industry_research"
  | "debate"
  | "risk"
  | "master";

const RESEARCH_SKILL_IDS = new Set([
  "skill_stock_research",
  "skill_market_research",
  "skill_industry_research",
]);

function primarySkill(process: StreamState): SkillStep | undefined {
  if (process.activeSkillRunId) {
    return process.skillSteps.find((s) => s.skillRunId === process.activeSkillRunId);
  }
  return process.skillSteps[process.skillSteps.length - 1];
}

function skillToFlow(skillId: string): ProcessFlow | null {
  switch (skillId) {
    case "skill_stock_research":
      return "stock_research";
    case "skill_market_research":
      return "market_research";
    case "skill_industry_research":
      return "industry_research";
    case "skill_bull_bear_debate":
      return "debate";
    case "skill_risk_checkup":
      return "risk";
    case "skill_master_commentary":
      return "master";
    default:
      return null;
  }
}

function inferDimensionKind(process: StreamState): DimensionKind {
  const skill = primarySkill(process);
  if (skill?.skillId === "skill_market_research") return "market";
  if (skill?.skillId === "skill_industry_research") return "industry";
  const statusText = `${process.streamStatus}\n${process.streamLog.join("\n")}`;
  const defs = detectDimensionSet(process.agentSteps, statusText);
  if (defs.length >= 5 || statusText.includes("五维")) return "industry";
  if (
    process.agentSteps.some((s) => s.agent_id === "macro" || s.agent_id === "industry") ||
    (statusText.includes("市场") && statusText.includes("四维"))
  ) {
    return "market";
  }
  return "stock";
}

function sliceHasDebate(slice: SkillStreamSlice): boolean {
  return slice.debateRounds.length > 0 || slice.judgeVerdict != null || slice.voteTally != null;
}

function looksLikePlanExecute(process: StreamState): boolean {
  const blob = `${process.streamStatus}\n${process.streamLog.join("\n")}`;
  return (
    /status\.plan|执行步骤|规划执行|plan\.synthesizing|综合分析/i.test(blob) ||
    process.streamLog.some((line) => /步骤\s*\d+\s*\/\s*\d+/.test(line))
  );
}

/** Classify backend workflow for process panel labeling. */
export function detectProcessFlow(process: StreamState): ProcessFlow {
  const skill = primarySkill(process);
  if (skill) {
    const fromSkill = skillToFlow(skill.skillId);
    if (fromSkill) return fromSkill;
  }

  for (const step of process.skillSteps) {
    const flow = skillToFlow(step.skillId);
    if (flow) return flow;
  }

  if (process.agentSteps.some((s) => isRiskWorkflowAgent(s.agent_id))) {
    return "risk";
  }

  if (
    process.debateRounds.length > 0 ||
    process.voteTally != null ||
    process.skillSteps.some((s) => sliceHasDebate(s.nested))
  ) {
    const hasResearchSkill = process.skillSteps.some((s) => RESEARCH_SKILL_IDS.has(s.skillId));
    if (!hasResearchSkill) return "debate";
  }

  if (process.agentSteps.some((s) => isDimensionAgent(s.agent_id))) {
    const kind = inferDimensionKind(process);
    if (kind === "market") return "market_research";
    if (kind === "industry") return "industry_research";
    return "stock_research";
  }

  if (process.masterCommentary.length > 0) return "master";

  if (looksLikePlanExecute(process)) return "plan";

  return "react";
}

type TFn = (key: string, params?: Record<string, string | number>) => string;

function dimensionSlugs(flow: ProcessFlow, t: TFn): string | null {
  if (flow === "stock_research") {
    return dimensionDefsForKind("stock", t)
      .map((d) => d.name)
      .join("/");
  }
  if (flow === "market_research") {
    return dimensionDefsForKind("market", t)
      .map((d) => d.name)
      .join("/");
  }
  if (flow === "industry_research") {
    return dimensionDefsForKind("industry", t)
      .map((d) => d.name)
      .join("/");
  }
  return null;
}

function flowLabel(flow: ProcessFlow, live: boolean, t: TFn): string {
  const key = live ? `chat.processLive.${flow}` : `chat.processTitle.${flow}`;
  const dims = dimensionSlugs(flow, t);
  if (dims) return t(key, { dims });
  return t(key);
}

export function processTrailLabel(
  process: StreamState | undefined,
  live: boolean,
  t: TFn,
  override?: string,
): string {
  if (override) return override;
  const flow = process ? detectProcessFlow(process) : "react";
  return flowLabel(flow, live, t);
}

export function skillStepLabel(skill: SkillStep, t: TFn): string {
  const flow = skillToFlow(skill.skillId);
  if (flow) return flowLabel(flow, skill.status === "running", t);
  return skill.label;
}

