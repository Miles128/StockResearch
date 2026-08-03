import type { LlmUsage } from "./api";

export function formatLlmUsage(
  usage: LlmUsage,
  t: (key: string) => string,
): string {
  const cost =
    usage.estimated_cost_cny != null
      ? ` · ${t("chat.usageCost").replace("{cost}", usage.estimated_cost_cny.toFixed(4))}`
      : "";
  const estimate = usage.is_estimate ? ` (${t("chat.usageEstimate")})` : "";
  return (
    t("chat.usageLine")
      .replace("{total}", String(usage.total_tokens))
      .replace("{prompt}", String(usage.prompt_tokens))
      .replace("{completion}", String(usage.completion_tokens)) +
    cost +
    estimate
  );
}

export function formatHeaderUsage(
  usage: LlmUsage,
  t: (key: string) => string,
): string {
  return t("header.usageShort").replace("{total}", String(usage.total_tokens));
}
