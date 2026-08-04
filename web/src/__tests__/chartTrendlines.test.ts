import { describe, expect, it } from "vitest";
import type { KlineBar } from "../chartIndicators";
import { detectTrendLines, findPivots } from "../chartTrendlines";

/** Synthetic ascending channel: lows bounce on S(i)=98+0.5i, highs cap at R(i)=112+0.5i. */
function channelBars(n: number, slope = 0.5, touchEvery = 10): KlineBar[] {
  const bars: KlineBar[] = [];
  for (let i = 0; i < n; i += 1) {
    const support = 98 + slope * i;
    const resistance = 112 + slope * i;
    const lowTouch = i % touchEvery === 5;
    const highTouch = i % touchEvery === 0;
    const low = lowTouch ? support : support + 2;
    const high = highTouch ? resistance : resistance - 2;
    const close = (low + high) / 2;
    bars.push({
      date: `D${String(i).padStart(3, "0")}`,
      open: close,
      high,
      low,
      close,
      volume: 1000,
    });
  }
  return bars;
}

describe("findPivots", () => {
  it("detects swing highs and lows on a clean channel", () => {
    const bars = channelBars(61);
    const { highs, lows } = findPivots(bars, 3);
    expect(lows.map((p) => p.index)).toEqual([5, 15, 25, 35, 45, 55]);
    expect(highs.map((p) => p.index)).toEqual([10, 20, 30, 40, 50]);
  });
});

describe("detectTrendLines", () => {
  it("finds the ascending support and resistance lines of the channel", () => {
    const bars = channelBars(61);
    const lines = detectTrendLines(bars);
    const support = lines.find((l) => l.kind === "support");
    const resistance = lines.find((l) => l.kind === "resistance");

    expect(support).toBeDefined();
    expect(support!.slopePerBar).toBeCloseTo(0.5, 5);
    expect(support!.endPrice).toBeCloseTo(98 + 0.5 * 60, 5);
    expect(support!.touches).toBeGreaterThanOrEqual(2);

    expect(resistance).toBeDefined();
    expect(resistance!.slopePerBar).toBeCloseTo(0.5, 5);
    expect(resistance!.endPrice).toBeCloseTo(112 + 0.5 * 60, 5);
  });

  it("rejects a support line that was broken near the end", () => {
    const bars = channelBars(61);
    // Deep breach below the ascending support at bar 59.
    bars[59] = { ...bars[59], low: 90, close: 95, open: 95 };
    const lines = detectTrendLines(bars);
    expect(lines.some((l) => l.kind === "support")).toBe(false);
  });

  it("filters out lines far from the latest close", () => {
    // Flat channel around 98-112, then a rally holding above the old support.
    const rally: KlineBar[] = Array.from({ length: 20 }, (_, i) => {
      const low = 128 + i * 0.5;
      const high = low + 8;
      const close = low + 4;
      return {
        date: `R${String(i).padStart(2, "0")}`,
        open: close,
        high,
        low,
        close,
        volume: 1,
      };
    });
    const bars = [...channelBars(40, 0), ...rally];
    const lines = detectTrendLines(bars);
    // The stale horizontal support near 98 must be dropped as irrelevant.
    expect(lines.some((l) => l.kind === "support" && l.endPrice < 105)).toBe(false);
  });

  it("returns empty for short series", () => {
    expect(detectTrendLines(channelBars(8))).toEqual([]);
    expect(detectTrendLines([])).toEqual([]);
  });

  it("respects maxLines", () => {
    const bars = channelBars(61);
    const lines = detectTrendLines(bars, { maxLines: 1 });
    expect(lines.length).toBeLessThanOrEqual(1);
  });
});
