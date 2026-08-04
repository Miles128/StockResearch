import { useEffect, type Dispatch, type SetStateAction } from "react";
import type { HoldingEnriched, StockQuoteOut } from "../api";
import type { FocusTab } from "../focusTabs";

/** Keep stock focus tabs' price/change_pct in sync with fresh holdings & watchlist quotes. */
export function useFocusTabQuoteSync(
  setFocusTabs: Dispatch<SetStateAction<FocusTab[]>>,
  holdings: HoldingEnriched[],
  watchlistQuotes: Record<string, StockQuoteOut>,
): void {
  useEffect(() => {
    setFocusTabs((tabs) => {
      let changed = false;
      const next = tabs.map((tab) => {
        if (tab.context.kind !== "stock") return tab;
        const sym = tab.context.symbol;
        const holding = holdings.find((h) => h.symbol === sym);
        const quote = watchlistQuotes[sym];
        const price = holding?.price ?? quote?.price ?? tab.context.price;
        const change_pct = holding?.change_pct ?? quote?.change_pct ?? tab.context.change_pct;
        if (price === tab.context.price && change_pct === tab.context.change_pct) return tab;
        changed = true;
        return { ...tab, context: { ...tab.context, price, change_pct } };
      });
      return changed ? next : tabs;
    });
  }, [setFocusTabs, holdings, watchlistQuotes]);
}
