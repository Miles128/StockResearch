/**
 * Tiny pub/sub channel for Copilot chart overlays (Phase 9b):
 * the chat card publishes an AI ChartOverlaySet, the focused StockChart
 * subscribes and renders it through the same line-series path as the
 * local auto trendlines.
 */

import type { ChartOverlaySet } from "./api";

type Listener = (set: ChartOverlaySet | null) => void;

const listeners = new Set<Listener>();

export function publishChartOverlays(set: ChartOverlaySet | null): void {
  for (const listener of listeners) listener(set);
}

export function subscribeChartOverlays(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
