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
