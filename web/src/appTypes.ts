import type { ChatResponse, LlmUsage } from "./api";
import type { StreamState } from "./streamEvents";

export type Tab = "portfolio" | "risk" | "market" | "news";

export interface CopilotContext {
  kind: "portfolio" | "risk" | "market" | "news" | "stock" | "report";
  label: string;
  detail?: string;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  cards?: ChatResponse["cards"];
  intent?: string;
  followUpQuestions?: string[];
  llmUsage?: LlmUsage | null;
  process?: StreamState;
}
