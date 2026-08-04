import { useEffect } from "react";
import type { HoldingEnriched } from "../api";

interface QuotePollingOptions {
  enabled: boolean;
  quoteRefreshMinutes: number;
  loadHoldings: (opts?: { silent?: boolean }) => Promise<HoldingEnriched[]>;
  refreshWatchlistQuotes: (opts?: { silent?: boolean }) => Promise<void>;
}

/** PRD §七: UI 轮询默认关。开启后按交易时段/休市节奏刷新持仓与自选行情。 */
export function useQuotePolling({
  enabled,
  quoteRefreshMinutes,
  loadHoldings,
  refreshWatchlistQuotes,
}: QuotePollingOptions): void {
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timeoutId = 0;
    const tradingPollMs = 30_000;
    const closedPollMs = Math.max(quoteRefreshMinutes, 1) * 60_000;

    async function refreshQuotes() {
      if (cancelled || document.hidden) {
        timeoutId = window.setTimeout(refreshQuotes, tradingPollMs);
        return;
      }
      try {
        const data = await loadHoldings({ silent: true });
        await refreshWatchlistQuotes({ silent: true });
        if (cancelled) return;
        const trading = data.some((h) => h.market_session === "trading");
        timeoutId = window.setTimeout(refreshQuotes, trading ? tradingPollMs : closedPollMs);
      } catch {
        if (!cancelled) {
          timeoutId = window.setTimeout(refreshQuotes, tradingPollMs);
        }
      }
    }

    timeoutId = window.setTimeout(refreshQuotes, tradingPollMs);
    return () => {
      cancelled = true;
      if (timeoutId) window.clearTimeout(timeoutId);
    };
  }, [enabled, quoteRefreshMinutes, loadHoldings, refreshWatchlistQuotes]);
}
