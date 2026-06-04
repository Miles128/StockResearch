export type AnalysisMode = "simple" | "complex";

const RISK_KEYWORDS = ["风险", "止损", "仓位", "体检", "回撤", "持仓安全", "危险"];

export function shouldAskAnalysisMode(message: string): boolean {
  const msg = message.trim();
  return !RISK_KEYWORDS.some((kw) => msg.includes(kw));
}

export function analysisModeLabel(mode: AnalysisMode): string {
  return mode === "simple" ? "简单分析" : "复杂分析（Multi-Agent）";
}
