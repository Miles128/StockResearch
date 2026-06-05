import type { AgentStep } from "./StreamFeed";

export interface DimensionDef {
  id: string;
  name: string;
}

export const STOCK_DIMENSIONS: DimensionDef[] = [
  { id: "fundamental", name: "基本面" },
  { id: "technical", name: "技术面" },
  { id: "sentiment", name: "情绪面" },
  { id: "chips", name: "筹码面" },
];

export const MARKET_DIMENSIONS: DimensionDef[] = [
  { id: "macro", name: "宏观面" },
  { id: "industry", name: "行业面" },
  { id: "technical", name: "技术面" },
  { id: "sentiment", name: "情绪面" },
];

export const DIMENSION_AGENT_IDS = new Set([
  ...STOCK_DIMENSIONS.map((d) => d.id),
  ...MARKET_DIMENSIONS.map((d) => d.id),
]);

export function isDimensionAgent(agentId: string): boolean {
  return DIMENSION_AGENT_IDS.has(agentId);
}

export function detectDimensionSet(
  steps: AgentStep[],
  statusText: string,
): DimensionDef[] {
  if (steps.some((s) => s.agent_id === "macro" || s.agent_id === "industry")) {
    return MARKET_DIMENSIONS;
  }
  if (statusText.includes("市场") && statusText.includes("四维")) {
    return MARKET_DIMENSIONS;
  }
  return STOCK_DIMENSIONS;
}

export function seedDimensionSteps(
  steps: AgentStep[],
  defs: DimensionDef[],
): AgentStep[] {
  const next = [...steps];
  for (const def of defs) {
    if (next.some((s) => s.agent_id === def.id)) continue;
    next.push({
      agent_id: def.id,
      agent_name: def.name,
      role: "analyst",
      status: "pending",
      content: "",
    });
  }
  return next;
}

export function orderedDimensionSteps(
  steps: AgentStep[],
  defs: DimensionDef[],
): AgentStep[] {
  const byId = new Map(
    steps.filter((s) => isDimensionAgent(s.agent_id)).map((s) => [s.agent_id, s]),
  );
  return defs.map(
    (def) =>
      byId.get(def.id) ?? {
        agent_id: def.id,
        agent_name: def.name,
        role: "analyst",
        status: "pending" as const,
        content: "",
      },
  );
}

export function dimensionsComplete(dimSteps: AgentStep[]): boolean {
  return (
    dimSteps.length === 4 &&
    dimSteps.every((s) => s.status === "done")
  );
}

export function dimensionPhaseActive(dimSteps: AgentStep[]): boolean {
  return dimSteps.some((s) => s.status !== "pending");
}
