import { useCallback, useRef, useState } from "react";
import { api, type AgentStreamEvent, type RiskCheckup } from "../api";
import {
  applyStreamEvent,
  emptyStreamState,
  finalizeStreamState,
  type StreamState,
} from "../streamEvents";
import { normalizeStreamEvent, translateStatusEvent } from "../streamI18n";

export interface RiskState {
  risk: RiskCheckup | null;
  riskLoading: boolean;
  riskStream: StreamState;
  riskStatusMsg: string;
  runRisk: () => Promise<void>;
}

export function useRiskCheckup(
  onError?: (msg: string) => void,
  t?: (key: string, params?: Record<string, string | number>) => string,
): RiskState {
  const [risk, setRisk] = useState<RiskCheckup | null>(null);
  const [riskLoading, setRiskLoading] = useState(false);
  const [riskStream, setRiskStream] = useState<StreamState>(emptyStreamState);
  const [riskStatusMsg, setRiskStatusMsg] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  const runRisk = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setRiskLoading(true);
    setRiskStream(emptyStreamState());
    setRiskStatusMsg("");

    const translate = t ?? ((key: string) => key);

    try {
      const result = await api.riskCheckupStream((event: AgentStreamEvent) => {
        if (event.type === "risk_snapshot" && event.result) {
          setRisk(event.result as unknown as RiskCheckup);
        }
        if (event.type === "status") {
          setRiskStatusMsg(translateStatusEvent(event, translate));
        }
        const normalized = normalizeStreamEvent(event, translate);
        setRiskStream((prev) => applyStreamEvent(prev, normalized, translate));
      }, controller.signal);

      if (result) {
        setRisk(result);
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        onError?.(String(e));
      }
    } finally {
      setRiskLoading(false);
      setRiskStream((prev) =>
        finalizeStreamState(prev, translate("chat.analysisDone")),
      );
      abortRef.current = null;
    }
  }, [onError, t]);

  return { risk, riskLoading, riskStream, riskStatusMsg, runRisk };
}
