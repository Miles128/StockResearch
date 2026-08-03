/**
 * Batch research entry assembly: dedupe + cap watchlist symbols.
 */

export const BATCH_RESEARCH_LIMIT = 8;

export function planBatchResearchSymbols(
  symbols: Array<string | null | undefined>,
  limit: number = BATCH_RESEARCH_LIMIT,
): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of symbols) {
    const s = (raw ?? "").trim();
    if (!s || seen.has(s)) continue;
    seen.add(s);
    out.push(s);
    if (out.length >= limit) break;
  }
  return out;
}

export function batchResearchSummary(
  items: Array<{
    report?: unknown;
    error?: string | null;
  }>,
): { ok: number; failed: number } {
  let ok = 0;
  let failed = 0;
  for (const item of items) {
    if (item.report) ok += 1;
    else failed += 1;
  }
  return { ok, failed };
}
