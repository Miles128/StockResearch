import type { ChatResponse, LlmUsage } from "./api";
import type { StreamState } from "./streamEvents";

export type Tab = "portfolio" | "risk" | "market" | "news" | "daily_scan";

export interface CopilotContext {
  kind: "portfolio" | "risk" | "market" | "news" | "daily_scan" | "stock" | "report";
  label: string;
  detail?: string;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  cards?: ChatResponse["cards"];
  intent?: string;
  llmUsage?: LlmUsage | null;
  process?: StreamState;
}
