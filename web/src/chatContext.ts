import type { CopilotContext } from "./appTypes";

export function copilotContextToPayload(context: CopilotContext): {
  kind: CopilotContext["kind"];
  label: string;
  detail?: string;
  symbol?: string;
  metadata?: Record<string, string>;
} {
  const symbolMatch = context.label.match(/\b(\d{6})\b/);
  return {
    kind: context.kind,
    label: context.label,
    detail: context.detail,
    symbol: symbolMatch?.[1],
  };
}
