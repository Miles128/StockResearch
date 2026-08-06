import { describe, expect, it } from "vitest";
import type { KlineBar } from "../chartIndicators";
import { detectTrendLines } from "../chartTrendlines";
import contractFixture from "../../../tests/contracts/fixtures/chart_overlay_contract.json";

/**
 * 跨端画线契约：前端算法跑共享 fixture（chart_overlay_contract.json），
 * 输出必须与 Python 后端一致（tests/contracts/test_chart_overlay_contract.py
 * 断言同一 fixture）——两端漂移即失败。
 */

const bars: KlineBar[] = contractFixture.bars.map((b) => ({
  date: b.date,
  open: b.close,
  high: b.high,
  low: b.low,
  close: b.close,
  volume: 1000,
}));

function compareContract(actual: ReturnType<typeof detectTrendLines>) {
  expect(actual.length).toBe(contractFixture.trend_lines.length);
  const byKind = (kind: "support" | "resistance") =>
    actual.filter((l) => l.kind === kind).sort((a, b) => b.touches - a.touches);
  const expectedByKind = (kind: string) =>
    contractFixture.trend_lines
      .filter((l) => l.kind === kind)
      .sort((a, b) => b.touches - a.touches);

  for (const kind of ["support", "resistance"] as const) {
    const got = byKind(kind);
    const exp = expectedByKind(kind);
    expect(got.length).toBe(exp.length);
    for (let i = 0; i < got.length; i += 1) {
      expect(got[i].slopePerBar).toBeCloseTo(exp[i].slope_per_bar, 5);
      expect(got[i].endPrice).toBeCloseTo(exp[i].end_price, 3);
      expect(got[i].touches).toBe(exp[i].touches);
    }
  }
}

describe("chart overlay cross-stack contract", () => {
  it("detectTrendLines matches the Python backend on the shared fixture", () => {
    compareContract(detectTrendLines(bars));
  });
});
