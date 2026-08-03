import { describe, expect, it } from "vitest";
import {
  atrSeries,
  bollSeries,
  buildIndicators,
  kdjSeries,
  maSeries,
  mergeKlineBars,
  rsiSeries,
} from "../chartIndicators";

describe("chartIndicators", () => {
  it("computes MA20 after enough bars", () => {
    const closes = Array.from({ length: 25 }, (_, i) => 10 + i * 0.1);
    const ma = maSeries(closes, 20);
    expect(ma[18]).toBeNull();
    expect(ma[19]).toBeTypeOf("number");
    expect(ma[24]).toBeTypeOf("number");
  });

  it("merges older bars without duplicates", () => {
    const existing = [
      { date: "2024-01-02", open: 1, high: 1, low: 1, close: 1, volume: 1 },
      { date: "2024-01-03", open: 2, high: 2, low: 2, close: 2, volume: 2 },
    ];
    const older = [
      { date: "2024-01-01", open: 0, high: 0, low: 0, close: 0, volume: 0 },
      { date: "2024-01-02", open: 9, high: 9, low: 9, close: 9, volume: 9 },
    ];
    const merged = mergeKlineBars(older, existing);
    expect(merged.map((b) => b.date)).toEqual([
      "2024-01-01",
      "2024-01-02",
      "2024-01-03",
    ]);
    expect(merged[1].close).toBe(1);
  });

  it("buildIndicators matches bar count including boll/atr/kdj", () => {
    const closes = Array.from({ length: 40 }, (_, i) => 100 + Math.sin(i / 3));
    const highs = closes.map((c) => c + 1);
    const lows = closes.map((c) => c - 1);
    const ind = buildIndicators(closes, highs, lows);
    expect(ind.ma20).toHaveLength(40);
    expect(ind.rsi).toHaveLength(40);
    expect(ind.macd).toHaveLength(40);
    expect(ind.boll_mid).toHaveLength(40);
    expect(ind.atr).toHaveLength(40);
    expect(ind.kdj_k).toHaveLength(40);
    expect(rsiSeries(closes)[14]).toBeTypeOf("number");
    expect(bollSeries(closes).upper[19]).toBeTypeOf("number");
    expect(atrSeries(highs, lows, closes)[14]).toBeTypeOf("number");
    expect(kdjSeries(highs, lows, closes).k[8]).toBeTypeOf("number");
  });
});
