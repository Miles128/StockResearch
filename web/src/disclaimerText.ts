const DISCLAIMER_PATTERNS = [
  /以下内容由\s*AI\s*生成[，,]\s*仅供参考[，,]\s*不构成投资建议[。.]?\s*/gi,
  /以上内容由\s*AI\s*生成[，,]\s*仅供参考[，,]\s*不构成投资建议[。.]?\s*/gi,
  /本产品所有\s*AI\s*输出仅供学习参考[，,]\s*不构成投资建议[。.]?\s*/gi,
];

export function stripDisclaimer(text: string): string {
  if (!text) return "";
  let result = text;
  for (const pattern of DISCLAIMER_PATTERNS) {
    result = result.replace(pattern, "");
  }
  return result.trim();
}

export function isResearchTurn(
  cards?: { type: string }[],
  intent?: string,
): boolean {
  if (intent === "research") return true;
  return Boolean(cards?.some((c) => c.type === "research"));
}
