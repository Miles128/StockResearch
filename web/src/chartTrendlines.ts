/**
 * Client-side automatic trendline detection.
 *
 * Finds fractal pivot highs/lows on the OHLC series, then fits candidate
 * support/resistance lines through pivot pairs. A line is kept only if the
 * price respected it (no close/wick breach beyond a tolerance) from the first
 * anchor all the way to the latest bar, so the result reflects trendlines that
 * are still "active". Each line is scored by how many pivots touch it and how
 * long it spans, then de-duplicated and ranked.
 */

import type { KlineBar } from "./chartIndicators";

export interface Pivot {
  index: number;
  price: number;
}

export type TrendLineKind = "support" | "resistance";

export interface TrendLine {
  kind: TrendLineKind;
  /** First anchor bar index. */
  startIndex: number;
  /** Bar index the line is extended to (latest bar). */
  endIndex: number;
  startPrice: number;
  /** Value of the line at endIndex. */
  endPrice: number;
  slopePerBar: number;
  touches: number;
}

export interface TrendLineOptions {
  /** Fractal look-forward/back window for pivots. Default 3. */
  pivotWindow?: number;
  /** Relative tolerance for a touch/breach. Default 0.006 (0.6%). */
  tolerancePct?: number;
  /** Max number of lines returned. Default 4. */
  maxLines?: number;
  /** Min bars between the two anchors. Default 5. */
  minSpan?: number;
  /** Max bars between the two anchors. Default 140. */
  maxSpan?: number;
  /** Drop lines whose extended end is farther than this fraction from the last close. Default 0.15. */
  relevancePct?: number;
}

export function findPivots(
  bars: KlineBar[],
  k: number,
): { highs: Pivot[]; lows: Pivot[] } {
  const highs: Pivot[] = [];
  const lows: Pivot[] = [];
  for (let i = k; i < bars.length - k; i += 1) {
    let isHigh = true;
    let isLow = true;
    for (let j = i - k; j <= i + k; j += 1) {
      if (bars[j].high > bars[i].high) isHigh = false;
      if (bars[j].low < bars[i].low) isLow = false;
      if (!isHigh && !isLow) break;
    }
    if (isHigh) highs.push({ index: i, price: bars[i].high });
    if (isLow) lows.push({ index: i, price: bars[i].low });
  }
  return { highs, lows };
}

function scoreLine(
  line: TrendLine,
  maxSpan: number,
  lastClose: number,
): number {
  const span = line.endIndex - line.startIndex;
  const spanScore = Math.min(span, maxSpan) / maxSpan;
  // Prefer lines that matter now: penalize distance from the latest close.
  const distance = Math.abs(line.endPrice - lastClose) / lastClose;
  return line.touches * 2 + spanScore - distance * 10;
}

function isDuplicate(
  a: TrendLine,
  b: TrendLine,
  tolerancePct: number,
): boolean {
  if (a.kind !== b.kind) return false;
  const nearStart =
    Math.abs(a.startPrice - b.startPrice) <= tolerancePct * 2 * a.startPrice;
  const nearEnd =
    Math.abs(a.endPrice - b.endPrice) <= tolerancePct * 2 * a.endPrice;
  return nearStart && nearEnd;
}

function fitLines(
  bars: KlineBar[],
  pivots: Pivot[],
  kind: TrendLineKind,
  opts: Required<TrendLineOptions>,
): TrendLine[] {
  const last = bars.length - 1;
  const { tolerancePct, minSpan, maxSpan } = opts;
  const out: TrendLine[] = [];

  for (let a = 0; a < pivots.length; a += 1) {
    for (let b = a + 1; b < pivots.length; b += 1) {
      const p1 = pivots[a];
      const p2 = pivots[b];
      const span = p2.index - p1.index;
      if (span < minSpan || span > maxSpan) continue;

      const slope = (p2.price - p1.price) / span;
      const valueAt = (idx: number) => p1.price + slope * (idx - p1.index);

      // The line must be respected from the first anchor to the latest bar.
      let valid = true;
      for (let t = p1.index; t <= last; t += 1) {
        const lv = valueAt(t);
        const tol = tolerancePct * lv;
        if (kind === "support") {
          if (bars[t].low < lv - tol) {
            valid = false;
            break;
          }
        } else if (bars[t].high > lv + tol) {
          valid = false;
          break;
        }
      }
      if (!valid) continue;

      // Count pivots of the same kind that touch the line.
      let touches = 0;
      for (const p of pivots) {
        if (p.index < p1.index) continue;
        const lv = valueAt(p.index);
        if (Math.abs(p.price - lv) <= tolerancePct * lv) touches += 1;
      }
      if (touches < 2) continue;

      out.push({
        kind,
        startIndex: p1.index,
        endIndex: last,
        startPrice: p1.price,
        endPrice: valueAt(last),
        slopePerBar: slope,
        touches,
      });
    }
  }

  return out;
}

export function detectTrendLines(
  bars: KlineBar[],
  options: TrendLineOptions = {},
): TrendLine[] {
  const opts: Required<TrendLineOptions> = {
    pivotWindow: options.pivotWindow ?? 3,
    tolerancePct: options.tolerancePct ?? 0.006,
    maxLines: options.maxLines ?? 4,
    minSpan: options.minSpan ?? 5,
    maxSpan: options.maxSpan ?? 140,
    relevancePct: options.relevancePct ?? 0.15,
  };
  const { pivotWindow, tolerancePct, maxLines, maxSpan, relevancePct } = opts;
  if (bars.length < opts.minSpan + 2 * pivotWindow + 2) return [];

  const lastClose = bars[bars.length - 1].close;
  const relevant = (line: TrendLine) =>
    Math.abs(line.endPrice - lastClose) / lastClose <= relevancePct;

  const { highs, lows } = findPivots(bars, pivotWindow);
  const supports = fitLines(bars, lows, "support", opts).filter(relevant);
  const resistances = fitLines(bars, highs, "resistance", opts).filter(
    relevant,
  );

  const pick = (lines: TrendLine[], cap: number): TrendLine[] => {
    const sorted = lines
      .slice()
      .sort(
        (x, y) =>
          scoreLine(y, maxSpan, lastClose) - scoreLine(x, maxSpan, lastClose),
      );
    const kept: TrendLine[] = [];
    for (const line of sorted) {
      if (kept.length >= cap) break;
      if (kept.some((k) => isDuplicate(k, line, tolerancePct))) continue;
      kept.push(line);
    }
    return kept;
  };

  const half = Math.ceil(maxLines / 2);
  return [...pick(supports, half), ...pick(resistances, half)].slice(
    0,
    maxLines,
  );
}

/** Build the two render points for a trendline (anchor start -> extended end). */
export function trendLinePoints(
  line: TrendLine,
  bars: KlineBar[],
): { index: number; price: number }[] {
  return [
    { index: line.startIndex, price: line.startPrice },
    { index: line.endIndex, price: line.endPrice },
  ];
}
