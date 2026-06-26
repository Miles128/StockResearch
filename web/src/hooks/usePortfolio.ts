import { useCallback, useEffect, useState } from "react";
import { api, type HoldingEnriched } from "../api";

export interface PortfolioState {
  holdings: HoldingEnriched[];
  holdingsLoading: boolean;
  isDemo: boolean;
  demoLoading: boolean;
  loadHoldings: () => Promise<void>;
  loadDemoHoldings: () => Promise<void>;
  clearDemoHoldings: () => Promise<void>;
}

export function usePortfolio(onError?: (msg: string) => void): PortfolioState {
  const [holdings, setHoldings] = useState<HoldingEnriched[]>([]);
  const [holdingsLoading, setHoldingsLoading] = useState(false);
  const [isDemo, setIsDemo] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);

  const loadHoldings = useCallback(async () => {
    try {
      setHoldingsLoading(true);
      const data = await api.holdingsEnriched();
      setHoldings(data);
      if (data.length === 0) {
        try {
          await api.loadDemo();
          setHoldings(await api.holdingsEnriched());
          setIsDemo(true);
        } catch {
          // ignore auto-load failures
        }
      }
    } catch (e) {
      onError?.(String(e));
    } finally {
      setHoldingsLoading(false);
    }
  }, [onError]);

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
      api.demoStatus().then((s) => setIsDemo(s.demo)).catch(() => {});
    });
  }, [loadHoldings]);

  return {
    holdings,
    holdingsLoading,
    isDemo,
    demoLoading,
    loadHoldings,
    loadDemoHoldings,
    clearDemoHoldings,
  };
}
