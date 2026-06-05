import type { ChatResponse, LlmUsage } from "./api";
import type { StreamState } from "./streamEvents";

export type Tab = "chat" | "news" | "portfolio" | "risk" | "settings";

export interface Message {
  role: "user" | "assistant";
  content: string;
  cards?: ChatResponse["cards"];
  intent?: string;
  llmUsage?: LlmUsage | null;
  process?: StreamState;
}
