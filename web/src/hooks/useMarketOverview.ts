import { useCallback, useEffect, useState } from "react";
import { api, type DataSourceStatus, type MarketOverview } from "../api";

export interface MarketOverviewState {
  marketOverview: MarketOverview | null;
  overviewLoading: boolean;
  dataStatus: DataSourceStatus | null;
  loadOverview: () => Promise<void>;
  refreshDataStatus: () => void;
}

export function useMarketOverview(): MarketOverviewState {
  const [marketOverview, setMarketOverview] = useState<MarketOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [dataStatus, setDataStatus] = useState<DataSourceStatus | null>(null);

  const refreshDataStatus = useCallback(() => {
    void api.dataSourceStatus().then(setDataStatus).catch(() => setDataStatus(null));
  }, []);

  const loadOverview = useCallback(async () => {
    try {
      setOverviewLoading(true);
      setMarketOverview(await api.marketOverview());
      refreshDataStatus();
    } catch {
      setMarketOverview(null);
    } finally {
      setOverviewLoading(false);
    }
  }, [refreshDataStatus]);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  return {
    marketOverview,
    overviewLoading,
    dataStatus,
    loadOverview,
    refreshDataStatus,
  };
}
