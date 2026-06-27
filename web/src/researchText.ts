const PUNCT = ["。", "；", "！", "？", ".", ";"] as const;

function compressToMax(plain: string, maxLen: number): string {
  if (plain.length <= maxLen) return plain;
  const slice = plain.slice(0, maxLen);
  const lastPunct = Math.max(...PUNCT.map((p) => slice.lastIndexOf(p)));
  if (lastPunct >= Math.floor(maxLen * 0.55)) {
    return plain.slice(0, lastPunct + 1);
  }
  return `${plain.slice(0, maxLen - 1)}…`;
}

function joinParts(parts: string[]): string {
  const cleaned = parts.map((p) => p.trim().replace(/。+$/, "")).filter(Boolean);
  if (!cleaned.length) return "";
  const text = cleaned.join("。");
  return text.endsWith("。") ? text : `${text}。`;
}

export interface NormalizeResearchConclusionOptions {
  minLen?: number;
  maxLen?: number;
  /** Extra sentences used to lengthen short conclusions (e.g. dimension highlights). */
  expandHints?: string[];
}

/** Fit composite conclusion into ~120–180 chars by compressing or expanding. */
export function normalizeResearchConclusion(
  text: string,
  { minLen = 120, maxLen = 180, expandHints = [] }: NormalizeResearchConclusionOptions = {},
): string {
  const trimmed = text.trim();
  if (!trimmed) return trimmed;
  const plain = trimmed.replace(/\s+/g, " ");

  if (plain.length >= minLen && plain.length <= maxLen) {
    return trimmed;
  }

  if (plain.length > maxLen) {
    return compressToMax(plain, maxLen);
  }

  const parts = [plain.replace(/。+$/, "")];
  const seen = new Set<string>([plain]);

  for (const raw of expandHints) {
    const hint = raw.trim().replace(/。+$/, "");
    if (!hint || seen.has(hint)) continue;
    seen.add(hint);
    const candidate = joinParts([...parts, hint]);
    if (candidate.length >= minLen && candidate.length <= maxLen) {
      return candidate;
    }
    if (candidate.length > maxLen) {
      return compressToMax(candidate, maxLen);
    }
    parts.push(hint);
  }

  const result = joinParts(parts);
  return result || trimmed;
}

/** @deprecated Use normalizeResearchConclusion */
export function clipResearchConclusion(text: string, maxLen = 180): string {
  return normalizeResearchConclusion(text, { maxLen, minLen: 0 });
}

export function researchExpandHintsFromReport(report: {
  dimensions?: Record<string, { highlights?: string[]; risks?: string[] }>;
  debate?: { consensus?: string; core_divergence?: string } | null;
}): string[] {
  const hints: string[] = [];
  for (const dim of Object.values(report.dimensions ?? {})) {
    for (const line of dim.highlights ?? []) {
      if (line.trim() && !hints.includes(line.trim())) hints.push(line.trim());
      if (hints.length >= 6) break;
    }
    if (hints.length >= 6) break;
  }
  if (report.debate?.consensus?.trim()) {
    hints.push(report.debate.consensus.trim());
  } else if (report.debate?.core_divergence?.trim()) {
    hints.push(report.debate.core_divergence.trim());
  }
  return hints;
}
