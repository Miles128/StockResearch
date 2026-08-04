import type { AgentStep } from "./types/streamTypes";

/** Risk checkup pipeline agent ids (matches backend stream.py). */
export const RISK_WORKFLOW_AGENT_IDS = new Set([
  "rules",
  "market",
  "correlation",
  "scenario",
  "research_manager",
  "judge",
]);

export const RISK_AGENT_ORDER = [
  "rules",
  "market",
  "correlation",
  "scenario",
  "research_manager",
  "judge",
] as const;

export function isRiskWorkflowAgent(agentId: string): boolean {
  return RISK_WORKFLOW_AGENT_IDS.has(agentId);
}

export function isRiskWorkflow(steps: AgentStep[], statusText = ""): boolean {
  if (steps.some((s) => isRiskWorkflowAgent(s.agent_id))) return true;
  return /风控|risk checkup|status\.risk/i.test(statusText);
}

export function orderedRiskWorkflowSteps(steps: AgentStep[]): AgentStep[] {
  const byId = new Map(steps.map((s) => [s.agent_id, s]));
  return RISK_AGENT_ORDER.filter((id) => byId.has(id)).map((id) => byId.get(id)!);
}

export function seedRiskWorkflowSteps(steps: AgentStep[], t: (key: string) => string): AgentStep[] {
  const byId = new Map(steps.map((s) => [s.agent_id, s]));
  const next = [...steps];
  for (const id of RISK_AGENT_ORDER) {
    if (byId.has(id)) continue;
    const label = t(`stream.agents.${id}`);
    const name = label !== `stream.agents.${id}` ? label : id;
    next.push({
      agent_id: id,
      agent_name: name,
      role:
        id === "rules"
          ? "rules"
          : id === "judge"
            ? "judge"
            : id === "research_manager"
              ? "manager"
              : "analyst",
      status: "pending",
      content: "",
    });
    byId.set(id, next[next.length - 1]!);
  }
  return next;
}

export function riskWorkflowPhaseActive(steps: AgentStep[]): boolean {
  return steps.some((s) => isRiskWorkflowAgent(s.agent_id) && s.status !== "pending");
}
