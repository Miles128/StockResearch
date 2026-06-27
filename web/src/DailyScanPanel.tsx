import { useEffect, useState } from "react";
import { api, type DailyScanOut, type DailyScanItem, type HoldingEnriched } from "./api";
import { useI18n } from "./i18n";

interface DailyScanPanelProps {
  holdings: HoldingEnriched[];
  numLocale: string;
  onAnalyzeHolding: (h: HoldingEnriched) => void;
}

function signalClass(signal: string): string {
  if (signal === "bullish") return "up";
  if (signal === "bearish") return "down";
  return "muted";
}

export function DailyScanPanel({ holdings, numLocale, onAnalyzeHolding }: DailyScanPanelProps) {
  const { t } = useI18n();
  const [data, setData] = useState<DailyScanOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadScan() {
    if (holdings.length === 0) return;
    setLoading(true);
    setError("");
    try {
      setData(await api.dailyScan());
    } catch (e) {
      setError(String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (holdings.length > 0 && !data && !loading) {
      void loadScan();
    }
  }, [holdings.length]);

  function handleAnalyze(item: DailyScanItem) {
    const h = holdings.find((x) => x.symbol === item.symbol);
    if (h) onAnalyzeHolding(h);
  }

  if (holdings.length === 0) {
    return (
      <div className="panel">
        <div className="risk-empty-cta">
          <p className="muted">{t("dailyScan.emptyHoldings")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="panel daily-scan-panel">
      <div className="daily-scan-header">
        <div>
          <h2 className="panel-title">{t("dailyScan.title")}</h2>
          {data && (
            <p className="muted daily-scan-date">
              {t("dailyScan.date", { date: data.scan_date })}
            </p>
          )}
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => void loadScan()}
          disabled={loading}
        >
          {loading ? t("dailyScan.loading") : t("dailyScan.refresh")}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {data && (
        <>
          <div className="card daily-scan-summary">
            <p>{data.summary}</p>
          </div>

          <div className="daily-scan-list">
            {data.items.map((item) => (
              <div
                key={item.symbol}
                className={`daily-scan-item signal-${item.signal}`}
                onClick={() => handleAnalyze(item)}
                role="button"
                tabIndex={0}
              >
                <div className="daily-scan-item-head">
                  <div className="daily-scan-stock">
                    <strong>{item.name}</strong>
                    <span className="muted">{item.symbol}</span>
                    <span className="daily-scan-sector">{item.sector}</span>
                  </div>
                  <div className="daily-scan-tags">
                    <span className="daily-scan-score">
                      {t("dailyScan.score")} {item.technical_score.toFixed(1)}
                    </span>
                    <span className={`stat-pill ${signalClass(item.signal)}`}>
                      {item.signal_text}
                    </span>
                  </div>
                </div>

                <div className="daily-scan-metrics">
                  <div>
                    <span className="muted">{t("dailyScan.price")}</span>
                    <span className="mono">{item.price?.toFixed(2) ?? "-"}</span>
                  </div>
                  <div>
                    <span className="muted">{t("dailyScan.change")}</span>
                    <span className={`mono ${(item.change_pct ?? 0) >= 0 ? "up" : "down"}`}>
                      {item.change_pct != null ? `${item.change_pct >= 0 ? "+" : ""}${item.change_pct.toFixed(2)}%` : "-"}
                    </span>
                  </div>
                  <div>
                    <span className="muted">{t("dailyScan.cost")}</span>
                    <span className="mono">{item.cost_price.toFixed(2)}</span>
                  </div>
                  <div>
                    <span className="muted">{t("dailyScan.profit")}</span>
                    <span className={`mono ${(item.profit_pct ?? 0) >= 0 ? "up" : "down"}`}>
                      {item.profit_pct != null ? `${item.profit_pct >= 0 ? "+" : ""}${(item.profit_pct * 100).toFixed(2)}%` : "-"}
                    </span>
                  </div>
                </div>

                <div className="daily-scan-suggestion">
                  <span className="daily-scan-action">{item.suggestion}</span>
                </div>

                {item.factors.length > 0 && (
                  <ul className="daily-scan-factors">
                    {item.factors.map((f, i) => (
                      <li key={i} className="muted">
                        {f}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>

          <p className="turn-disclaimer">{data.disclaimer}</p>
        </>
      )}

      {!data && !loading && !error && (
        <div className="daily-scan-empty">
          <p className="muted">{t("dailyScan.hint")}</p>
          <button type="button" className="btn btn-primary" onClick={() => void loadScan()}>
            {t("dailyScan.run")}
          </button>
        </div>
      )}
    </div>
  );
}
