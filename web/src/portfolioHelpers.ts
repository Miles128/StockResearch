import type { HoldingEnriched } from "./api";
import { computeDailyPnlAmount } from "./holdingDisplay";

export interface PortfolioSummary {
  count: number;
  totalValue: number;
  totalCost: number;
  totalProfit: number;
  totalProfitPct: number | null;
  annualizedPct: number | null;
  todayPnl: number;
  todayPnlPct: number | null;
  hasQuotes: boolean;
}

export interface SectorWeight {
  sector: string;
  pct: number;
  value: number;
  count: number;
  todayPnl: number;
  totalProfit: number;
  annualizedPct: number | null;
}

export function computePortfolioSummary(
  holdings: HoldingEnriched[],
): PortfolioSummary {
  let totalValue = 0;
  let totalCost = 0;
  let totalProfit = 0;
  let todayPnl = 0;
  let hasQuotes = false;
  let weightedAnnualized = 0;
  let annualizedWeight = 0;

  for (const h of holdings) {
    if (!h.quote_available || h.price == null) continue;
    hasQuotes = true;
    const mv = h.price * h.quantity;
    const costBasis = h.cost_price * h.quantity;
    totalValue += mv;
    totalCost += costBasis;
    if (h.profit_amount != null) {
      totalProfit += h.profit_amount;
    } else {
      totalProfit += mv - costBasis;
    }
    const daily = computeDailyPnlAmount(h.price, h.quantity, h.change_pct);
    if (daily != null) todayPnl += daily;
    if (h.annualized_pct != null && mv > 0) {
      weightedAnnualized += h.annualized_pct * mv;
      annualizedWeight += mv;
    }
  }

  const totalProfitPct = totalCost > 0 ? (totalProfit / totalCost) * 100 : null;
  const annualizedPct =
    annualizedWeight > 0 ? weightedAnnualized / annualizedWeight : null;
  const priorValue = totalValue - todayPnl;
  const todayPnlPct = priorValue > 0 ? (todayPnl / priorValue) * 100 : null;

  return {
    count: holdings.length,
    totalValue,
    totalCost,
    totalProfit,
    totalProfitPct,
    annualizedPct,
    todayPnl,
    todayPnlPct,
    hasQuotes,
  };
}

export function computeSectorConcentration(
  holdings: HoldingEnriched[],
): SectorWeight[] {
  const bySector = new Map<
    string,
    {
      value: number;
      count: number;
      todayPnl: number;
      totalProfit: number;
      annualizedNum: number;
      annualizedDen: number;
    }
  >();
  let total = 0;
  for (const h of holdings) {
    const sector = h.sector?.trim() || "未知";
    const entry = bySector.get(sector) ?? {
      value: 0,
      count: 0,
      todayPnl: 0,
      totalProfit: 0,
      annualizedNum: 0,
      annualizedDen: 0,
    };
    entry.count += 1;
    if (h.quote_available && h.price != null) {
      const mv = h.price * h.quantity;
      const costBasis = h.cost_price * h.quantity;
      total += mv;
      entry.value += mv;
      const daily = computeDailyPnlAmount(h.price, h.quantity, h.change_pct);
      if (daily != null) entry.todayPnl += daily;
      if (h.profit_amount != null) {
        entry.totalProfit += h.profit_amount;
      } else {
        entry.totalProfit += mv - costBasis;
      }
      if (h.annualized_pct != null && mv > 0) {
        entry.annualizedNum += h.annualized_pct * mv;
        entry.annualizedDen += mv;
      }
    }
    bySector.set(sector, entry);
  }
  if (total <= 0) return [];
  return [...bySector.entries()]
    .filter(([, entry]) => entry.value > 0)
    .map(([sector, entry]) => ({
      sector,
      value: entry.value,
      pct: (entry.value / total) * 100,
      count: entry.count,
      todayPnl: entry.todayPnl,
      totalProfit: entry.totalProfit,
      annualizedPct:
        entry.annualizedDen > 0
          ? entry.annualizedNum / entry.annualizedDen
          : null,
    }))
    .sort((a, b) => b.pct - a.pct);
}
