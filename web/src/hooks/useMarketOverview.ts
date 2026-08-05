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
    void api
      .dataSourceStatus()
      .then(setDataStatus)
      .catch(() => setDataStatus(null));
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
    // 挂载时发起加载：同步设置 loading 属惯用加载模式
    // eslint-disable-next-line react-hooks/set-state-in-effect
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
