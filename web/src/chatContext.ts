import type { CopilotContext } from "./appTypes";

export function copilotContextToPayload(context: CopilotContext): {
  kind: CopilotContext["kind"];
  label: string;
  detail?: string;
  symbol?: string;
  metadata?: Record<string, string>;
} {
  const symbolFromLabel = context.label.match(/\b(\d{6})\b/)?.[1];
  const symbolFromDetail =
    context.detail && /^\d{6}$/.test(context.detail)
      ? context.detail
      : undefined;
  const sectorMatch = context.detail?.match(/^板块：(.+)$/);
  return {
    kind: context.kind,
    label: context.label,
    detail: context.detail,
    symbol: symbolFromDetail ?? symbolFromLabel,
    metadata: sectorMatch?.[1] ? { sector: sectorMatch[1] } : undefined,
  };
}
