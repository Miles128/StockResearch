import { useEffect, useRef, useState } from "react";
import {
  api,
  type AgentStreamEvent,
  type NewsAnalysis,
  type NewsAnalysisStockImpact,
} from "./api";
import { useI18n } from "./i18n";
import { localizeSentiment, localizeImpactLevel } from "./uiLabels";
import { translateStatusEvent } from "./streamI18n";

interface Props {
  newsId: number;
  title: string;
  summary: string;
  source: string;
  sentiment: string;
  impactLevel: string;
  entities: string[];
  onClose: () => void;
}

const STOCK_RE = /^\d{6}$/;

type NewsAnalysisPhase =
  "pick" | "connecting" | "fetching" | "analyzing" | "done";

const NEWS_STEP_ORDER = ["connecting", "fetching", "analyzing"] as const;

function phaseRank(phase: NewsAnalysisPhase): number {
  if (phase === "pick" || phase === "done") return phase === "done" ? 99 : -1;
  return NEWS_STEP_ORDER.indexOf(phase as (typeof NEWS_STEP_ORDER)[number]);
}

export function NewsAnalysisModal({
  newsId,
  title,
  summary,
  source,
  sentiment,
  impactLevel,
  entities,
  onClose,
}: Props) {
  const { t } = useI18n();
  const stockEntities = entities.filter((e) => STOCK_RE.test(e));
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [manualSymbol, setManualSymbol] = useState("");
  const [phase, setPhase] = useState<NewsAnalysisPhase>("pick");
  const [statusMsg, setStatusMsg] = useState("");
  const [stockImpact, setStockImpact] =
    useState<NewsAnalysisStockImpact | null>(null);
  const [analysis, setAnalysis] = useState<NewsAnalysis | null>(null);
  const [error, setError] = useState("");
  const [dimmed, setDimmed] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const raf = requestAnimationFrame(() => setDimmed(false));
    return () => cancelAnimationFrame(raf);
  }, []);

  function startAnalysis(symbol: string) {
    setSelectedSymbol(symbol);
    setPhase("connecting");
    setError("");
    setStockImpact(null);
    setAnalysis(null);

    const controller = new AbortController();
    abortRef.current = controller;

    void api
      .analyzeNews(
        newsId,
        symbol,
        (event: AgentStreamEvent) => {
          if (event.type === "status") {
            const msg = translateStatusEvent(event, t);
            setStatusMsg(msg);
            const key = (event.message_key as string) || "";
            if (key.includes("fetching")) setPhase("fetching");
            else if (key.includes("cross") || key.includes("analyze"))
              setPhase("analyzing");
          } else if (event.type === "stock_impact") {
            setPhase("analyzing");
            setStockImpact({
              symbol: (event.symbol as string) || symbol,
              name: (event.name as string) || "",
              price: 0,
              change_pct: 0,
              pe_ttm: null,
              technical_signal: "neutral",
              technical_summary: "",
              fundamental_summary: "",
              sentiment_summary: "",
              impact_assessment: (event.assessment as string) || "",
              impact_direction:
                (event.direction as "positive" | "negative" | "neutral") ||
                "neutral",
              key_points: (event.key_points as string[]) || [],
            });
          } else if (event.type === "done" && event.result) {
            const result = event.result as unknown as NewsAnalysis;
            setAnalysis(result);
            if (result.related_stocks?.length) {
              setStockImpact(result.related_stocks[0]);
            }
            setPhase("done");
          } else if (event.type === "error") {
            setError(String(event.message || "新闻分析失败"));
            setPhase("pick");
          }
        },
        controller.signal,
      )
      .catch((err) => {
        if ((err as Error).name !== "AbortError") {
          setError(String(err));
          setPhase("pick");
        }
      })
      .finally(() => {
        abortRef.current = null;
      });

    return () => {
      controller.abort();
    };
  }

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === e.currentTarget) onClose();
  }

  function impactIcon(dir: string): string {
    if (dir === "positive") return "↑";
    if (dir === "negative") return "↓";
    return "→";
  }

  function impactClass(dir: string): string {
    if (dir === "positive") return "up";
    if (dir === "negative") return "down";
    return "";
  }

  return (
    <div
      className={`modal-overlay${dimmed ? " modal-dimmed" : ""}`}
      onClick={handleOverlayClick}
    >
      <div className="modal news-analysis-modal">
        <div className="modal-header">
          <div>
            <span className="modal-badge">{t("news.deepAnalysisBadge")}</span>
            <span className="modal-badge modal-badge-muted">
              {t("news.deepAnalysisMode")}
            </span>
            <span
              className={`stat-pill ${sentiment === "bullish" ? "up" : sentiment === "bearish" ? "down" : ""}`}
            >
              {localizeSentiment(sentiment, t)} ·{" "}
              {localizeImpactLevel(impactLevel, t)}
            </span>
          </div>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="modal-body">
          <h3 className="news-analysis-title">{title}</h3>
          <p className="muted" style={{ fontSize: 13 }}>
            {summary} · {source}
          </p>

          {phase === "pick" && (
            <div className="news-pick-stock">
              {stockEntities.length > 0 ? (
                <>
                  <p className="news-pick-prompt">{t("news.selectStock")}</p>
                  <div className="news-stock-picker">
                    {stockEntities.map((symbol) => (
                      <button
                        key={symbol}
                        className="btn btn-primary"
                        onClick={() => startAnalysis(symbol)}
                      >
                        {symbol}
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <div className="news-pick-stock">
                  <p className="muted">{t("news.noStockEntities")}</p>
                  <p className="news-pick-prompt">{t("news.enterSymbol")}</p>
                  <div className="news-stock-picker">
                    <input
                      className="news-symbol-input"
                      inputMode="numeric"
                      maxLength={6}
                      placeholder="600519"
                      value={manualSymbol}
                      onChange={(e) =>
                        setManualSymbol(
                          e.target.value.replace(/\D/g, "").slice(0, 6),
                        )
                      }
                    />
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={manualSymbol.length !== 6}
                      onClick={() => startAnalysis(manualSymbol)}
                    >
                      {t("news.startAnalysis")}
                    </button>
                  </div>
                </div>
              )}
              {error && (
                <p className="error" style={{ marginTop: 10 }}>
                  {error}
                </p>
              )}
            </div>
          )}

          {phase !== "pick" && phase !== "done" && (
            <div className="news-analysis-loading">
              <div className="spinner" />
              <div className="news-analysis-progress">
                <p style={{ margin: 0, fontWeight: 600 }}>{selectedSymbol}</p>
                <ol className="news-analysis-steps">
                  {NEWS_STEP_ORDER.map((step) => {
                    const active = phase === step;
                    const done =
                      phaseRank(phase) > phaseRank(step as NewsAnalysisPhase);
                    return (
                      <li
                        key={step}
                        className={`news-analysis-step${active ? " active" : ""}${done ? " done" : ""}`}
                      >
                        {t(`news.step.${step}`)}
                      </li>
                    );
                  })}
                </ol>
                {statusMsg && (
                  <p className="news-analysis-status muted">{statusMsg}</p>
                )}
              </div>
            </div>
          )}

          {phase === "done" && stockImpact && (
            <div className="news-stock-impacts">
              <div className="card" style={{ marginBottom: 16 }}>
                <div className="news-stock-header">
                  <strong>{stockImpact.name}</strong>
                  <code>{stockImpact.symbol}</code>
                  <span
                    className={`stat-pill ${impactClass(stockImpact.impact_direction)}`}
                  >
                    {impactIcon(stockImpact.impact_direction)}{" "}
                    {stockImpact.price.toFixed(2)}{" "}
                    <span
                      className={stockImpact.change_pct >= 0 ? "up" : "down"}
                    >
                      {stockImpact.change_pct >= 0 ? "+" : ""}
                      {stockImpact.change_pct.toFixed(2)}%
                    </span>
                  </span>
                  {stockImpact.pe_ttm != null && (
                    <span className="stat-pill">
                      PE {stockImpact.pe_ttm.toFixed(1)}
                    </span>
                  )}
                  <span
                    className={`stat-pill ${stockImpact.technical_signal === "bullish" ? "up" : stockImpact.technical_signal === "bearish" ? "down" : ""}`}
                  >
                    {stockImpact.technical_signal === "bullish"
                      ? t("news.techBullish")
                      : stockImpact.technical_signal === "bearish"
                        ? t("news.techBearish")
                        : t("news.techNeutral")}
                  </span>
                </div>
              </div>

              {stockImpact.fundamental_summary && (
                <div className="card">
                  <h4>{t("news.fundamentalVerification")}</h4>
                  <p className="news-impact-text">
                    {stockImpact.fundamental_summary}
                  </p>
                </div>
              )}

              {stockImpact.technical_summary && (
                <div className="card">
                  <h4>{t("news.technicalVerification")}</h4>
                  <p className="news-impact-text">
                    {stockImpact.technical_summary}
                  </p>
                </div>
              )}

              {stockImpact.sentiment_summary && (
                <div className="card">
                  <h4>{t("news.sentimentVerification")}</h4>
                  <p className="news-impact-text">
                    {stockImpact.sentiment_summary}
                  </p>
                </div>
              )}

              {analysis?.market_context && (
                <div className="card">
                  <h4>{t("news.conclusion")}</h4>
                  <p className="news-impact-text">{analysis.market_context}</p>
                </div>
              )}

              {stockImpact.key_points.length > 0 && (
                <div className="card">
                  <h4>{t("news.keyPoints")}</h4>
                  <ul className="news-key-points">
                    {stockImpact.key_points.map((kp, i) => (
                      <li key={i}>{kp}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
