/** Portfolio NAV curve vs benchmark + trade ledger (decision journal) sections. */

import { useEffect, useMemo, useState } from "react";
import { api, type PortfolioPerformance, type TradeRecord } from "./api";
import { CollapsibleSection } from "./CollapsibleSection";
import { formatSignedMoney, formatSignedPct, signedClass } from "./holdingDisplay";
import { useI18n } from "./i18n";

const CHART_W = 220;
const CHART_H = 52;
const PERF_DAYS = 90;
const TRADE_LIMIT = 8;

function linePath(values: number[], allMin: number, allMax: number): string {
  if (values.length < 2) return "";
  const span = allMax - allMin || 1;
  const step = CHART_W / (values.length - 1);
  return values
    .map((v, i) => {
      const x = i * step;
      const y = CHART_H - 3 - ((v - allMin) / span) * (CHART_H - 6);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function PerfChart({ perf }: { perf: PortfolioPerformance }) {
  const { portfolio, benchmark, min, max } = useMemo(() => {
    const p = perf.series.map((pt) => pt.portfolio_index);
    const b = perf.series.map((pt) => pt.benchmark_index);
    const all = [...p, ...b];
    return {
      portfolio: p,
      benchmark: b,
      min: Math.min(...all),
      max: Math.max(...all),
    };
  }, [perf.series]);

  return (
    <svg
      className="ledger-perf-chart"
      viewBox={`0 0 ${CHART_W} ${CHART_H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="portfolio-vs-benchmark"
    >
      <path
        d={linePath(benchmark, min, max)}
        fill="none"
        stroke="var(--muted)"
        strokeWidth="1.5"
        strokeDasharray="4 3"
        opacity="0.8"
      />
      <path
        d={linePath(portfolio, min, max)}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function shortDate(iso: string | null, fallbackIso: string): string {
  const value = iso || fallbackIso;
  return value.slice(0, 10);
}

const BIAS_LABEL_KEYS: Record<string, string> = {
  bullish: "portfolio.biasBullish",
  bearish: "portfolio.biasBearish",
  neutral: "portfolio.biasNeutral",
};

export function PortfolioLedgerSections({ trigger }: { trigger: string }) {
  const { t } = useI18n();
  const [perf, setPerf] = useState<PortfolioPerformance | null>(null);
  const [trades, setTrades] = useState<TradeRecord[]>([]);

  useEffect(() => {
    let alive = true;
    Promise.allSettled([
      api.portfolioPerformance(PERF_DAYS),
      api.portfolioTrades(TRADE_LIMIT),
    ]).then(([perfResult, tradesResult]) => {
      if (!alive) return;
      if (perfResult.status === "fulfilled") setPerf(perfResult.value);
      if (tradesResult.status === "fulfilled") setTrades(tradesResult.value);
    });
    return () => {
      alive = false;
    };
  }, [trigger]);

  if (!perf && trades.length === 0) return null;

  const perfSummary =
    perf && perf.portfolio_return_pct != null ? (
      <span className={`ledger-perf-summary mono ${signedClass(perf.portfolio_return_pct)}`}>
        {formatSignedPct(perf.portfolio_return_pct)}
      </span>
    ) : undefined;

  return (
    <>
      {perf && (
        <CollapsibleSection title={t("portfolio.perfTitle")} summary={perfSummary}>
          {perf.series.length > 0 ? (
            <div className="ledger-perf-body">
              <PerfChart perf={perf} />
              <div className="ledger-perf-legend mono">
                <span className="ledger-perf-item">
                  <i className="ledger-perf-dot ledger-perf-dot-portfolio" />
                  {t("portfolio.perfPortfolio")}{" "}
                  <b className={signedClass(perf.portfolio_return_pct)}>
                    {formatSignedPct(perf.portfolio_return_pct)}
                  </b>
                </span>
                <span className="ledger-perf-item">
                  <i className="ledger-perf-dot ledger-perf-dot-benchmark" />
                  {perf.benchmark_name}{" "}
                  <b className={signedClass(perf.benchmark_return_pct)}>
                    {formatSignedPct(perf.benchmark_return_pct)}
                  </b>
                </span>
              </div>
              {perf.realized_pnl_total !== 0 && (
                <div className="ledger-perf-realized mono">
                  <span className="lists-metric-label">{t("portfolio.perfRealized")}</span>
                  <span className={signedClass(perf.realized_pnl_total)}>
                    {formatSignedMoney(perf.realized_pnl_total)}
                  </span>
                </div>
              )}
              <p className="muted ledger-perf-basis">
                {t("portfolio.perfBasis")}
                {perf.partial && perf.message ? ` · ${perf.message}` : ""}
              </p>
            </div>
          ) : (
            <p className="muted flat-empty">{perf.message || t("portfolio.perfEmpty")}</p>
          )}
        </CollapsibleSection>
      )}

      {trades.length > 0 && (
        <CollapsibleSection title={t("portfolio.tradesTitle")} defaultCollapsed>
          <ul className="ledger-trades">
            {trades.map((tr) => (
              <li key={tr.id} className="ledger-trade-row">
                <span className="mono ledger-trade-date">
                  {shortDate(tr.trade_date, tr.created_at)}
                </span>
                <span className={`ledger-trade-side ${tr.side === "buy" ? "buy" : "sell"}`}>
                  {tr.side === "buy" ? t("portfolio.tradeSideBuy") : t("portfolio.tradeSideSell")}
                </span>
                <span className="ledger-trade-name" title={tr.note || tr.name}>
                  {tr.name}
                  {tr.note && <i className="ledger-trade-note-flag" aria-hidden="true" />}
                  {tr.report_bias && BIAS_LABEL_KEYS[tr.report_bias] && (
                    <span
                      className={`ledger-trade-bias ${tr.report_bias}`}
                      title={`${t("portfolio.tradeReportTitle")} ${shortDate(tr.report_date, tr.created_at)}`}
                    >
                      {t(BIAS_LABEL_KEYS[tr.report_bias])}
                    </span>
                  )}
                </span>
                <span className="mono ledger-trade-qty">{tr.quantity / 100}</span>
                <span className="mono ledger-trade-price">{tr.price.toFixed(2)}</span>
                {tr.side === "sell" && (
                  <span className={`mono ledger-trade-pnl ${signedClass(tr.realized_pnl)}`}>
                    {tr.realized_pnl != null ? formatSignedMoney(tr.realized_pnl) : "—"}
                  </span>
                )}
              </li>
            ))}
          </ul>
          <p className="muted ledger-perf-basis">{t("portfolio.tradesHint")}</p>
        </CollapsibleSection>
      )}
    </>
  );
}
