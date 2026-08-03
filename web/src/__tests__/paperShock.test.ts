import { describe, expect, it } from "vitest";
import { computePaperShock } from "../paperShock";
import type { HoldingEnriched } from "../api";

function holding(
  partial: Partial<HoldingEnriched> &
    Pick<
      HoldingEnriched,
      "symbol" | "name" | "cost_price" | "quantity" | "sector"
    >,
): HoldingEnriched {
  return {
    price_label: "",
    market_session: "closed",
    quote_available: true,
    price: partial.price ?? partial.cost_price,
    ...partial,
  };
}

describe("paperShock", () => {
  it("shocks max sector only", () => {
    const holdings = [
      holding({
        symbol: "600519",
        name: "茅台",
        cost_price: 100,
        price: 100,
        quantity: 10,
        sector: "白酒",
      }),
      holding({
        symbol: "300750",
        name: "宁德",
        cost_price: 200,
        price: 200,
        quantity: 1,
        sector: "新能源",
      }),
    ];
    // total 1200; 白酒 1000 -> -10% = -100
    const result = computePaperShock(holdings, "max_sector", -0.1);
    expect(result).not.toBeNull();
    expect(result!.targetLabel).toBe("白酒");
    expect(result!.pnl).toBeCloseTo(-100, 5);
    expect(result!.pnlPct).toBeCloseTo(-100 / 1200, 5);
  });

  it("shocks top holding", () => {
    const holdings = [
      holding({
        symbol: "600519",
        name: "茅台",
        cost_price: 100,
        price: 100,
        quantity: 10,
        sector: "白酒",
      }),
      holding({
        symbol: "300750",
        name: "宁德",
        cost_price: 200,
        price: 200,
        quantity: 1,
        sector: "新能源",
      }),
    ];
    const result = computePaperShock(holdings, "top_holding", -0.2);
    expect(result!.targetLabel).toContain("600519");
    expect(result!.pnl).toBeCloseTo(-200, 5);
  });
});
