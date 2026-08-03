import { useEffect, useRef, useState } from "react";
import { api, type BatchResearch } from "./api";
import { useI18n } from "./i18n";
import { LightResearchCard } from "./LightResearchCard";
import type { AppMode } from "./modeSettings";
import {
  batchResearchSummary,
  planBatchResearchSymbols,
} from "./batchResearchPlan";

interface Props {
  symbols: string[];
  appMode: AppMode;
  onClose: () => void;
}

export function BatchResearchModal({ symbols, appMode, onClose }: Props) {
  const { t } = useI18n();
  const targets = planBatchResearchSymbols(symbols);
  const [result, setResult] = useState<BatchResearch | null>(null);
  const [error, setError] = useState("");
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current || targets.length === 0) return;
    startedRef.current = true;
    let cancelled = false;
    api
      .batchResearch(targets)
      .then((data) => {
        if (!cancelled) setResult(data);
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const summary = result ? batchResearchSummary(result.items) : null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal batch-research-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <span className="modal-badge">{t("batch.title")}</span>
            {targets.length > 0 && (
              <span className="modal-badge modal-badge-muted">
                {targets.length}
              </span>
            )}
            {summary && (
              <span className="modal-badge modal-badge-muted">
                {t("batch.success")} {summary.ok} · {t("batch.failed")}{" "}
                {summary.failed}
              </span>
            )}
          </div>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="modal-body">
          {targets.length === 0 && <p className="muted">{t("batch.empty")}</p>}
          {targets.length > 0 && !result && !error && (
            <p className="muted batch-research-loading">{t("batch.loading")}</p>
          )}
          {error && (
            <p className="error">
              {t("batch.error")}: {error}
            </p>
          )}
          {result && (
            <div className="batch-research-items">
              {result.items.map((item) =>
                item.report ? (
                  <LightResearchCard
                    key={item.symbol}
                    report={item.report}
                    appMode={appMode}
                  />
                ) : (
                  <div key={item.symbol} className="card batch-research-error">
                    <strong>
                      {item.name || item.symbol} ({item.symbol})
                    </strong>
                    {item.partial && (
                      <span className="stat-pill">{t("batch.partial")}</span>
                    )}
                    <p className="error">{item.error ?? t("batch.error")}</p>
                  </div>
                ),
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
