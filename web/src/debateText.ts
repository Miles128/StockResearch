/** Parse debate utterance into summary (visible) + detail (expandable). */

const SUMMARY_RE = /【摘要】\s*([^\n【]+)/;
const DETAIL_RE = /【详述】\s*([\s\S]*)/;
const COLLAPSE_MIN_LEN = 140;
const COLLAPSE_MIN_DETAIL = 36;

export interface ParsedDebateSpeech {
  summary: string;
  detail: string;
  full: string;
  collapsible: boolean;
}

export function parseDebateSpeech(text: string): ParsedDebateSpeech {
  const full = text.trim();
  if (!full) {
    return { summary: "", detail: "", full: "", collapsible: false };
  }

  const summaryMatch = full.match(SUMMARY_RE);
  const detailMatch = full.match(DETAIL_RE);
  if (summaryMatch) {
    const summary = summaryMatch[1].trim();
    const detail = detailMatch?.[1]?.trim() ?? "";
    const collapsible =
      detail.length >= COLLAPSE_MIN_DETAIL &&
      summary.length + detail.length >= COLLAPSE_MIN_LEN;
    return { summary, detail, full, collapsible };
  }

  if (full.length <= COLLAPSE_MIN_LEN) {
    return { summary: full, detail: "", full, collapsible: false };
  }

  const paragraphs = full.split(/\n+/).map((p) => p.trim()).filter(Boolean);
  const summary = paragraphs[0] ?? full.slice(0, 100);
  const detail = paragraphs.slice(1).join("\n").trim();
  const collapsible = detail.length >= COLLAPSE_MIN_DETAIL;
  return { summary, detail, full, collapsible };
}

/** Convert Research Manager JSON output to natural-language markdown. */
export function formatManagerContent(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return trimmed;

  // Try to parse JSON
  let parsed: Record<string, string> | null = null;
  try {
    const candidate = JSON.parse(trimmed);
    if (typeof candidate === "object" && candidate !== null && !Array.isArray(candidate)) {
      parsed = candidate as Record<string, string>;
    }
  } catch {
    // Not JSON — return as-is (possibly already markdown)
  }

  if (!parsed) {
    // If looks like a raw JSON string but parse failed, try to extract
    const jsonMatch = trimmed.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      try {
        const c = JSON.parse(jsonMatch[0]);
        if (typeof c === "object" && c !== null && !Array.isArray(c)) {
          parsed = c as Record<string, string>;
        }
      } catch {
        // give up
      }
    }
  }

  if (!parsed) return trimmed;

  const labels: Record<string, string> = {
    investment_thesis: "投资要点",
    key_risk: "核心风险",
    debate_summary: "辩论摘要",
    recommended_bias: "综合倾向",
  };

  const lines: string[] = [];
  for (const [key, value] of Object.entries(parsed)) {
    if (typeof value !== "string" || !value.trim()) continue;
    const label = labels[key] || key;
    lines.push(`**${label}**：${value.trim()}`);
  }

  return lines.length > 0 ? lines.join("\n\n") : trimmed;
}
