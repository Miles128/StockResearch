import { describe, it, expect } from "vitest";
import { computePortfolioSummary, computeSectorConcentration } from "../portfolioHelpers";
import type { HoldingEnriched } from "../api";

function makeHolding(overrides: Partial<HoldingEnriched> = {}): HoldingEnriched {
  return {
    symbol: "TEST",
    name: "Test Stock",
    cost_price: 100,
    quantity: 10,
    sector: "科技",
    quote_available: true,
    price: 120,
    change_pct: 2.5,
    price_label: "$120.00",
    market_session: "trading",
    ...overrides,
  };
}

describe("computePortfolioSummary", () => {
  const emptySummary = {
    count: 0,
    totalValue: 0,
    totalCost: 0,
    totalProfit: 0,
    totalProfitPct: null,
    annualizedPct: null,
    todayPnl: 0,
    todayPnlPct: null,
    hasQuotes: false,
  };

  it("returns zero values for empty holdings", () => {
    const result = computePortfolioSummary([]);
    expect(result).toEqual(emptySummary);
  });

  it("computes total value and PnL from holdings with quotes", () => {
    const holdings = [
      makeHolding({
        symbol: "A",
        price: 100,
        cost_price: 90,
        quantity: 10,
        change_pct: 2,
        profit_amount: 100,
        profit_pct: 11.11,
        annualized_pct: 20,
      }),
      makeHolding({
        symbol: "B",
        price: 200,
        cost_price: 210,
        quantity: 5,
        change_pct: -1,
        profit_amount: -50,
        profit_pct: -4.76,
        annualized_pct: -10,
      }),
    ];
    const result = computePortfolioSummary(holdings);
    expect(result.count).toBe(2);
    expect(result.totalValue).toBe(100 * 10 + 200 * 5);
    expect(result.totalCost).toBe(90 * 10 + 210 * 5);
    expect(result.totalProfit).toBeCloseTo(50);
    expect(result.totalProfitPct).toBeCloseTo((50 / 1950) * 100);
    expect(result.hasQuotes).toBe(true);
    expect(result.todayPnl).toBeCloseTo(10);
    expect(result.annualizedPct).toBeCloseTo(5);
    expect(result.todayPnlPct).toBeCloseTo((10 / 1990) * 100);
  });

  it("skips holdings without quotes", () => {
    const holdings = [
      makeHolding({ quote_available: false, price: null }),
      makeHolding({ symbol: "B", price: 50, quantity: 20, change_pct: 0 }),
    ];
    const result = computePortfolioSummary(holdings);
    expect(result.count).toBe(2);
    expect(result.totalValue).toBe(50 * 20);
    expect(result.hasQuotes).toBe(true);
  });

  it("sets hasQuotes to false when no holdings have quotes", () => {
    const holdings = [
      makeHolding({ quote_available: false, price: null }),
      makeHolding({ quote_available: false, price: null }),
    ];
    const result = computePortfolioSummary(holdings);
    expect(result.hasQuotes).toBe(false);
    expect(result.totalValue).toBe(0);
  });

  it("handles change_pct being null", () => {
    const holdings = [makeHolding({ price: 100, quantity: 10, change_pct: null })];
    const result = computePortfolioSummary(holdings);
    expect(result.totalValue).toBe(1000);
    expect(result.todayPnl).toBe(0);
  });
});

describe("computeSectorConcentration", () => {
  it("returns empty array for no holdings with quotes", () => {
    expect(computeSectorConcentration([])).toEqual([]);
  });

  it("computes sector weights and sorts by pct descending", () => {
    const holdings = [
      makeHolding({ sector: "科技", price: 100, quantity: 10, change_pct: 2, profit_amount: 200 }),
      makeHolding({ sector: "金融", price: 200, quantity: 5, change_pct: -1, profit_amount: -50 }),
      makeHolding({ sector: "科技", price: 50, quantity: 4, change_pct: 0, profit_amount: 20 }),
    ];
    const result = computeSectorConcentration(holdings);
    expect(result).toHaveLength(2);
    expect(result[0].sector).toBe("科技");
    expect(result[0].pct).toBeCloseTo((1200 / 2200) * 100);
    expect(result[0].count).toBe(2);
    expect(result[0].totalProfit).toBeCloseTo(220);
    expect(result[1].sector).toBe("金融");
    expect(result[1].totalProfit).toBeCloseTo(-50);
  });

  it("treats empty sector as '未知'", () => {
    const holdings = [
      makeHolding({ sector: "", price: 100, quantity: 10 }),
      makeHolding({ sector: "  ", price: 50, quantity: 4 }),
    ];
    const result = computeSectorConcentration(holdings);
    expect(result).toHaveLength(1);
    expect(result[0].sector).toBe("未知");
    expect(result[0].count).toBe(2);
  });

  it("skips holdings without quotes for weight but counts all holdings in sector", () => {
    const holdings = [
      makeHolding({ quote_available: false, price: null }),
      makeHolding({ sector: "科技", price: 100, quantity: 10 }),
    ];
    const result = computeSectorConcentration(holdings);
    expect(result).toHaveLength(1);
    expect(result[0].sector).toBe("科技");
    expect(result[0].pct).toBeCloseTo(100);
    expect(result[0].count).toBe(2);
  });
});
