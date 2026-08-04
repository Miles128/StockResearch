import { useCallback, useEffect, useState } from "react";
import { api, type StockQuoteOut, type WatchlistItem } from "../api";

export interface WatchlistState {
  watchlist: WatchlistItem[];
  watchlistQuotes: Record<string, StockQuoteOut>;
  watchlistLoading: boolean;
  loadWatchlist: () => Promise<void>;
  refreshWatchlistQuotes: (opts?: { silent?: boolean }) => Promise<void>;
  addWatchlistItem: (symbol: string, name: string) => Promise<void>;
  removeWatchlistItem: (id: number) => Promise<void>;
}

export function useWatchlist(onError?: (msg: string) => void): WatchlistState {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [watchlistQuotes, setWatchlistQuotes] = useState<Record<string, StockQuoteOut>>({});
  const [watchlistLoading, setWatchlistLoading] = useState(false);

  const refreshWatchlistQuotes = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (watchlist.length === 0) {
        setWatchlistQuotes({});
        return;
      }
      if (!opts?.silent) setWatchlistLoading(true);
      try {
        const quotes = await api.stockQuotes(watchlist.map((i) => i.symbol).join(","), {
          forceRefresh: opts?.silent,
        });
        const map: Record<string, StockQuoteOut> = {};
        for (const q of quotes) map[q.symbol] = q;
        setWatchlistQuotes(map);
      } catch {
        // keep last quotes on transient failures
      } finally {
        if (!opts?.silent) setWatchlistLoading(false);
      }
    },
    [watchlist],
  );

  const loadWatchlist = useCallback(async () => {
    try {
      setWatchlistLoading(true);
      const items = await api.watchlist();
      setWatchlist(items);
      if (items.length === 0) {
        setWatchlistQuotes({});
        return;
      }
      const quotes = await api.stockQuotes(items.map((i) => i.symbol).join(","));
      const map: Record<string, StockQuoteOut> = {};
      for (const q of quotes) map[q.symbol] = q;
      setWatchlistQuotes(map);
    } catch (e) {
      onError?.(String(e));
    } finally {
      setWatchlistLoading(false);
    }
  }, [onError]);

  const addWatchlistItem = useCallback(
    async (symbol: string, name: string) => {
      try {
        await api.addWatchlist({ symbol, name });
        await loadWatchlist();
      } catch (e) {
        onError?.(String(e));
      }
    },
    [loadWatchlist, onError],
  );

  const removeWatchlistItem = useCallback(
    async (id: number) => {
      try {
        await api.deleteWatchlist(id);
        await loadWatchlist();
      } catch (e) {
        onError?.(String(e));
      }
    },
    [loadWatchlist, onError],
  );

  useEffect(() => {
    void loadWatchlist();
  }, [loadWatchlist]);

  return {
    watchlist,
    watchlistQuotes,
    watchlistLoading,
    loadWatchlist,
    refreshWatchlistQuotes,
    addWatchlistItem,
    removeWatchlistItem,
  };
}
