import type { HoldingEnriched } from "./api";

export interface PortfolioSummary {
  count: number;
  totalValue: number;
  todayPnl: number;
  hasQuotes: boolean;
}

export interface SectorWeight {
  sector: string;
  pct: number;
  value: number;
  count: number;
}

export function computePortfolioSummary(holdings: HoldingEnriched[]): PortfolioSummary {
  let totalValue = 0;
  let todayPnl = 0;
  let hasQuotes = false;
  for (const h of holdings) {
    if (!h.quote_available || h.price == null) continue;
    hasQuotes = true;
    const mv = h.price * h.quantity;
    totalValue += mv;
    if (h.change_pct != null) {
      todayPnl += mv * (h.change_pct / 100);
    }
  }
  return { count: holdings.length, totalValue, todayPnl, hasQuotes };
}

export function computeSectorConcentration(holdings: HoldingEnriched[]): SectorWeight[] {
  const bySector = new Map<string, { value: number; count: number }>();
  let total = 0;
  for (const h of holdings) {
    const sector = h.sector?.trim() || "未知";
    const entry = bySector.get(sector) ?? { value: 0, count: 0 };
    entry.count += 1;
    if (h.quote_available && h.price != null) {
      const mv = h.price * h.quantity;
      total += mv;
      entry.value += mv;
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
    }))
    .sort((a, b) => b.pct - a.pct);
}
