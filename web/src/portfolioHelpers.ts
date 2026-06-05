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
  const bySector = new Map<string, number>();
  let total = 0;
  for (const h of holdings) {
    if (!h.quote_available || h.price == null) continue;
    const mv = h.price * h.quantity;
    total += mv;
    const sector = h.sector?.trim() || "未知";
    bySector.set(sector, (bySector.get(sector) ?? 0) + mv);
  }
  if (total <= 0) return [];
  return [...bySector.entries()]
    .map(([sector, value]) => ({ sector, value, pct: (value / total) * 100 }))
    .sort((a, b) => b.pct - a.pct);
}
