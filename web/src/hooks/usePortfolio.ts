import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Holding, type HoldingEnriched } from "../api";

export interface PortfolioState {
  holdings: HoldingEnriched[];
  holdingsLoading: boolean;
  holdingsRefreshing: boolean;
  isDemo: boolean;
  demoLoading: boolean;
  loadHoldings: (opts?: { silent?: boolean }) => Promise<HoldingEnriched[]>;
  loadDemoHoldings: () => Promise<void>;
  clearDemoHoldings: () => Promise<void>;
}

const HOLDINGS_SNAPSHOT_KEY = "sr.holdings.enriched.v1";

function readHoldingsSnapshot(): HoldingEnriched[] | null {
  try {
    const raw = sessionStorage.getItem(HOLDINGS_SNAPSHOT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as HoldingEnriched[];
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function writeHoldingsSnapshot(data: HoldingEnriched[]) {
  try {
    sessionStorage.setItem(HOLDINGS_SNAPSHOT_KEY, JSON.stringify(data));
  } catch {
    // ignore quota / private mode
  }
}

function placeholderEnriched(h: Holding): HoldingEnriched {
  return {
    ...h,
    price_label: "现价",
    market_session: "closed",
    quote_available: false,
  };
}

export function usePortfolio(
  onError?: (msg: string) => void,
  onDataStatusRefresh?: () => void,
): PortfolioState {
  const cachedSnapshot = readHoldingsSnapshot();
  const hadSnapshotRef = useRef(Boolean(cachedSnapshot?.length));
  const [holdings, setHoldings] = useState<HoldingEnriched[]>(
    cachedSnapshot ?? [],
  );
  const [holdingsLoading, setHoldingsLoading] = useState(
    !cachedSnapshot?.length,
  );
  const [holdingsRefreshing, setHoldingsRefreshing] = useState(false);
  const [isDemo, setIsDemo] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const autoDemoLoadRequested = useRef(false);

  const loadHoldings = useCallback(
    async (opts?: { silent?: boolean }): Promise<HoldingEnriched[]> => {
      const silent = opts?.silent ?? false;
      if (silent) {
        setHoldingsRefreshing(true);
      } else {
        setHoldingsLoading(true);
        if (!hadSnapshotRef.current) {
          // Show DB rows immediately so the list is not blank while quotes load.
          void api
            .holdings()
            .then((basic) => {
              if (basic.length > 0) {
                setHoldings(basic.map(placeholderEnriched));
              }
            })
            .catch(() => {});
        }
      }
      try {
        const data = await api.holdingsEnriched({ forceRefresh: silent });
        setHoldings(data);
        writeHoldingsSnapshot(data);
        if (!silent) {
          onDataStatusRefresh?.();
        }
        if (data.length === 0 && !autoDemoLoadRequested.current) {
          autoDemoLoadRequested.current = true;
          try {
            await api.loadDemo();
            const demoData = await api.holdingsEnriched();
            setHoldings(demoData);
            writeHoldingsSnapshot(demoData);
            setIsDemo(true);
            return demoData;
          } catch {
            // ignore auto-load failures
          }
        }
        return data;
      } catch (e) {
        onError?.(String(e));
        return [];
      } finally {
        if (silent) {
          setHoldingsRefreshing(false);
        } else {
          setHoldingsLoading(false);
        }
      }
    },
    [onDataStatusRefresh, onError],
  );

  const loadDemoHoldings = useCallback(async () => {
    try {
      setDemoLoading(true);
      await api.loadDemo();
      setIsDemo(true);
      await loadHoldings();
    } catch (e) {
      onError?.(String(e));
    } finally {
      setDemoLoading(false);
    }
  }, [loadHoldings, onError]);

  const clearDemoHoldings = useCallback(async () => {
    try {
      setDemoLoading(true);
      await api.clearDemo();
      setIsDemo(false);
      await loadHoldings();
    } catch (e) {
      onError?.(String(e));
    } finally {
      setDemoLoading(false);
    }
  }, [loadHoldings, onError]);

  useEffect(() => {
    void loadHoldings().then(() => {
      api
        .demoStatus()
        .then((s) => setIsDemo(s.demo))
        .catch(() => {});
    });
  }, [loadHoldings]);

  return {
    holdings,
    holdingsLoading,
    holdingsRefreshing,
    isDemo,
    demoLoading,
    loadHoldings,
    loadDemoHoldings,
    clearDemoHoldings,
  };
}
