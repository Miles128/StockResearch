/** Client-side paper portfolio shock (mirrors backend apply_price_shocks). */

import type { HoldingEnriched } from "./api";

export type ShockTarget = "top_holding" | "max_sector";

export interface PaperShockResult {
  target: ShockTarget;
  targetLabel: string;
  shockPct: number;
  portfolioValue: number;
  shockedValue: number;
  pnl: number;
  pnlPct: number;
}

function marketValue(h: HoldingEnriched): number {
  const price = h.price ?? h.cost_price;
  return price * h.quantity;
}

export function computePaperShock(
  holdings: HoldingEnriched[],
  target: ShockTarget,
  shockPct: number,
): PaperShockResult | null {
  const priced = holdings.filter((h) => marketValue(h) > 0);
  if (!priced.length) return null;
  const total = priced.reduce((sum, h) => sum + marketValue(h), 0);
  if (total <= 0) return null;

  let key: string;
  let label: string;
  if (target === "top_holding") {
    const top = priced.reduce((a, b) => (marketValue(a) >= marketValue(b) ? a : b));
    key = top.symbol;
    label = `${top.name}(${top.symbol})`;
  } else {
    const sectorValue = new Map<string, number>();
    for (const h of priced) {
      sectorValue.set(h.sector, (sectorValue.get(h.sector) ?? 0) + marketValue(h));
    }
    const maxSector = [...sectorValue.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
    if (!maxSector) return null;
    key = maxSector;
    label = maxSector;
  }

  let shocked = 0;
  for (const h of priced) {
    const match = target === "top_holding" ? h.symbol === key : h.sector === key;
    const price = h.price ?? h.cost_price;
    const shockedPrice = match ? price * (1 + shockPct) : price;
    shocked += shockedPrice * h.quantity;
  }
  const pnl = shocked - total;
  return {
    target,
    targetLabel: label,
    shockPct,
    portfolioValue: total,
    shockedValue: shocked,
    pnl,
    pnlPct: pnl / total,
  };
}
