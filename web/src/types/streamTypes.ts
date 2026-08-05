/** Stream / agent process domain types (UI-agnostic). */

export interface AgentStep {
  agent_id: string;
  agent_name: string;
  role: string;
  content?: string;
  status: "pending" | "running" | "done";
}

export interface HoldingAction {
  symbol: string;
  name: string;
  action: string;
  reason: string;
  priority?: string;
}

export interface JudgeVerdict {
  risk_level?: string;
  position_action?: string;
  summary: string;
  reason?: string;
  divergence?: string;
  verdict?: string;
  content?: string;
  analysis_process?: string;
  holding_actions?: HoldingAction[];
}
