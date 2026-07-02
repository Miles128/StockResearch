import type { KlineBar, KlineIndicators } from "./chartIndicators";
import { buildIndicators } from "./chartIndicators";
import type { KlineChart } from "./api";

const CACHE_MS = 5 * 60 * 1000;

interface CacheEntry {
  chart: KlineChart;
  fetchedAt: number;
}

const sessionCache = new Map<string, CacheEntry>();

export function getCachedKline(symbol: string): KlineChart | null {
  const entry = sessionCache.get(symbol);
  if (!entry) return null;
  if (Date.now() - entry.fetchedAt > CACHE_MS) {
    sessionCache.delete(symbol);
    return null;
  }
  return entry.chart;
}

export function setCachedKline(symbol: string, bars: KlineBar[]): KlineChart {
  const closes = bars.map((b) => b.close);
  const chart: KlineChart = {
    symbol,
    days: bars.length,
    bars,
    indicators: buildIndicators(closes),
  };
  sessionCache.set(symbol, { chart, fetchedAt: Date.now() });
  return chart;
}

export function patchCachedKline(symbol: string, bars: KlineBar[]): KlineChart {
  return setCachedKline(symbol, bars);
}

export function clearKlineCache(symbol?: string): void {
  if (symbol) sessionCache.delete(symbol);
  else sessionCache.clear();
}

export type { KlineBar, KlineIndicators };
