import { useCallback, useState } from "react";
import { api, type RiskCheckup } from "../api";

export interface RiskState {
  risk: RiskCheckup | null;
  riskLoading: boolean;
  runRisk: () => Promise<void>;
}

export function useRiskCheckup(onError?: (msg: string) => void): RiskState {
  const [risk, setRisk] = useState<RiskCheckup | null>(null);
  const [riskLoading, setRiskLoading] = useState(false);

  const runRisk = useCallback(async () => {
    try {
      setRiskLoading(true);
      setRisk(await api.riskCheckup());
    } catch (e) {
      onError?.(String(e));
    } finally {
      setRiskLoading(false);
    }
  }, [onError]);

  return { risk, riskLoading, runRisk };
}
