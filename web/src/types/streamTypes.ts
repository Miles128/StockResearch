/** Stream / agent process domain types (UI-agnostic). */

export interface AgentStep {
  agent_id: string;
  agent_name: string;
  role: string;
  content?: string;
  status: "pending" | "running" | "done";
}

export interface DebateRound {
  round: number;
  bull?: string;
  bear?: string;
  aggressive?: string;
  neutral?: string;
  neutral_view?: string;
  conservative?: string;
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

export interface VoteTally {
  bullish: number;
  bearish: number;
  neutral: number;
  leading?: string;
}
