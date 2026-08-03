import { describe, expect, it } from "vitest";
import {
  BATCH_RESEARCH_LIMIT,
  batchResearchSummary,
  planBatchResearchSymbols,
} from "../batchResearchPlan";

describe("planBatchResearchSymbols", () => {
  it("dedupes and trims symbols, keeping first-seen order", () => {
    expect(
      planBatchResearchSymbols([" 600519 ", "600519", "000858", "000858"]),
    ).toEqual(["600519", "000858"]);
  });

  it("drops empty/null entries", () => {
    expect(
      planBatchResearchSymbols(["", null, undefined, "  ", "600036"]),
    ).toEqual(["600036"]);
  });

  it(`caps at ${BATCH_RESEARCH_LIMIT} symbols`, () => {
    const symbols = Array.from({ length: 12 }, (_, i) => String(600000 + i));
    const out = planBatchResearchSymbols(symbols);
    expect(out).toHaveLength(BATCH_RESEARCH_LIMIT);
    expect(out[0]).toBe("600000");
    expect(out[BATCH_RESEARCH_LIMIT - 1]).toBe(
      String(600000 + BATCH_RESEARCH_LIMIT - 1),
    );
  });

  it("supports a custom limit", () => {
    expect(planBatchResearchSymbols(["a", "b", "c"], 2)).toEqual(["a", "b"]);
  });

  it("returns empty list for empty input", () => {
    expect(planBatchResearchSymbols([])).toEqual([]);
  });
});

describe("batchResearchSummary", () => {
  it("counts ok vs failed items", () => {
    expect(
      batchResearchSummary([
        { report: { symbol: "600519" } },
        { report: null, error: "boom" },
        { error: "x" },
      ]),
    ).toEqual({ ok: 1, failed: 2 });
  });

  it("handles empty list", () => {
    expect(batchResearchSummary([])).toEqual({ ok: 0, failed: 0 });
  });
});
