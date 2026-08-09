/**
 * Portfolio cockpit — “今日关注”首页的组合驾驶舱。
 *
 * 组合日线（90 天净值 vs 沪深300）+ 决策台账（交易记录）+ 组合事件（财报/解禁）。
 * 有持仓时替换原空状态引导中的市场速览，板块异动与快讯下沉到底部。
 */

import { useEffect, useMemo, useState } from "react";
import {
  api,
  type HoldingEnriched,
  type PortfolioPerformance,
  type ResearchTimeline,
  type TradeRecord,
} from "./api";
import { CollapsibleSection } from "./CollapsibleSection";
import { CounterfactualTeachingBlock } from "./CounterfactualTeachingBlock";
import { PortfolioEventsSection } from "./PortfolioEventsScreener";
import { formatSignedMoney, formatSignedPct, signedClass } from "./holdingDisplay";
import { useI18n } from "./i18n";
import type { PortfolioSummary } from "./portfolioHelpers";

const PERF_DAYS = 90;
const TRADE_LIMIT = 10;
const CHART_W = 480;
const CHART_H = 132;
const AXIS_Y_W = 48; // Y 轴标签区宽度（px）
const AXIS_X_H = 20; // X 轴标签区高度（px）
const Y_TICK_N = 5; // Y 轴刻度数（含两端）
const X_TICK_N = 5; // X 轴刻度数（含两端）

function linePath(values: number[], allMin: number, allMax: number): string {
  if (values.length < 2) return "";
  const span = allMax - allMin || 1;
  const step = CHART_W / (values.length - 1);
  return values
    .map((v, i) => {
      const x = i * step;
      const y = CHART_H - 6 - ((v - allMin) / span) * (CHART_H - 12);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

interface PerfTick {
  value: number;
  /** viewBox 内 y 坐标（顶 6 → 底 CHART_H-6） */
  y: number;
  /** 相对绘图区高度的百分比位置（用于 HTML 标签定位） */
  pct: number;
}

function CockpitPerfChart({ perf }: { perf: PortfolioPerformance }) {
  const { portfolio, benchmark, min, max, yTicks, xTicks } = useMemo(() => {
    const p = perf.series.map((pt) => pt.portfolio_index);
    const b = perf.series.map((pt) => pt.benchmark_index);
    const all = [...p, ...b];
    const lo = Math.min(...all);
    const hi = Math.max(...all);
    const span = hi - lo || 1;
    // Y 刻度：从顶到底均匀取值，与 linePath 的映射保持一致。
    const yTicks: PerfTick[] = Array.from({ length: Y_TICK_N }, (_, i) => {
      const r = i / (Y_TICK_N - 1); // 0=顶, 1=底
      return {
        value: hi - r * span,
        y: 6 + r * (CHART_H - 12),
        pct: ((6 + r * (CHART_H - 12)) / CHART_H) * 100,
      };
    });
    // X 刻度：首、1/4、1/2、3/4、末 对应的日期。
    const n = perf.series.length;
    const xTicks =
      n < 2
        ? []
        : Array.from({ length: X_TICK_N }, (_, i) => ({
            date: perf.series[Math.round((i / (X_TICK_N - 1)) * (n - 1))].date,
            x: (i / (X_TICK_N - 1)) * CHART_W,
          }));
    return { portfolio: p, benchmark: b, min: lo, max: hi, yTicks, xTicks };
  }, [perf.series]);

  return (
    <div
      className="cockpit-perf-chart-wrap"
      style={{ paddingLeft: AXIS_Y_W, paddingBottom: AXIS_X_H }}
    >
      <svg
        className="cockpit-perf-chart"
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="portfolio-vs-benchmark"
      >
        {/* 纵向网格线（X 刻度） */}
        {xTicks.map((tk) => (
          <line
            key={`gx-${tk.x}`}
            x1={tk.x}
            y1={6}
            x2={tk.x}
            y2={CHART_H - 6}
            className="cockpit-perf-grid"
          />
        ))}
        {/* 横向网格线（Y 刻度） */}
        {yTicks.map((tk) => (
          <line
            key={`gy-${tk.y}`}
            x1={0}
            y1={tk.y}
            x2={CHART_W}
            y2={tk.y}
            className="cockpit-perf-grid"
          />
        ))}
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
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {/* Y 轴标签（数值） */}
      <div
        className="cockpit-perf-axis-y mono"
        style={{ width: AXIS_Y_W, bottom: AXIS_X_H }}
        aria-hidden="true"
      >
        {yTicks.map((tk) => (
          <span key={tk.value} className="cockpit-perf-tick-y" style={{ top: `${tk.pct}%` }}>
            {tk.value.toFixed(3)}
          </span>
        ))}
      </div>
      {/* X 轴标签（日期 MM-DD） */}
      <div
        className="cockpit-perf-axis-x mono"
        style={{ left: AXIS_Y_W, height: AXIS_X_H }}
        aria-hidden="true"
      >
        {xTicks.map((tk, i) => (
          <span
            key={`${tk.date}-${i}`}
            className={`cockpit-perf-tick-x ${i === 0 ? "first" : i === xTicks.length - 1 ? "last" : "mid"}`}
            style={{ left: `${(tk.x / CHART_W) * 100}%` }}
          >
            {tk.date.slice(5)}
          </span>
        ))}
      </div>
    </div>
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

/** 白话解读：基于今日盈亏方向 + 持仓涨跌生成一句人话。 */
function plainTalk(
  holdings: HoldingEnriched[],
  summary: PortfolioSummary,
  t: (k: string, vars?: Record<string, string>) => string,
): string | null {
  if (!summary.hasQuotes) return t("portfolio.plainTodayNoQuote");
  const pct = summary.todayPnlPct;
  if (pct == null || Math.abs(pct) < 0.1) return t("portfolio.plainTodayPnlFlat");
  const quoted = holdings.filter((h) => h.quote_available && h.change_pct != null);
  if (quoted.length === 0) return null;
  const direction = pct > 0 ? 1 : -1;
  const tops = [...quoted]
    .sort((a, b) => direction * ((b.change_pct ?? 0) - (a.change_pct ?? 0)))
    .slice(0, 2)
    .map((h) => h.name);
  if (tops.length === 0) return null;
  return t("portfolio.plainTodayPnlUp", {
    verb: pct > 0 ? t("portfolio.plainTodayVerbUp") : t("portfolio.plainTodayVerbDown"),
    tops: tops.join("、"),
  });
}

interface PortfolioCockpitProps {
  holdingsCount: number;
  watchlistCount: number;
  portfolioSummary: PortfolioSummary | null;
  holdings: HoldingEnriched[];
  onSelectLeader: (symbol: string, name: string) => void;
}

export function PortfolioCockpit({
  holdingsCount,
  watchlistCount,
  portfolioSummary,
  holdings,
  onSelectLeader,
}: PortfolioCockpitProps) {
  const { t } = useI18n();
  const trigger = `${holdingsCount}:${watchlistCount}`;
  const [perf, setPerf] = useState<PortfolioPerformance | null>(null);
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [timelines, setTimelines] = useState<ResearchTimeline[]>([]);

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

  // 结论核对：对有研报结论的交易，拉取标的研报时间线（含事后收益）。
  useEffect(() => {
    let alive = true;
    const symbols = [
      ...new Set(
        trades.filter((tr) => tr.report_id != null && tr.report_bias).map((tr) => tr.symbol),
      ),
    ].slice(0, 3);
    if (symbols.length === 0) {
      // 无持仓报告时清空时间线：派生状态重置
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTimelines([]);
      return;
    }
    Promise.all(symbols.map((sym) => api.researchTimeline(sym).catch(() => null))).then((items) => {
      if (alive) setTimelines(items.filter((x): x is ResearchTimeline => x !== null));
    });
    return () => {
      alive = false;
    };
  }, [trades]);

  const perfSummary =
    perf && perf.portfolio_return_pct != null ? (
      <span className={`ledger-perf-summary mono ${signedClass(perf.portfolio_return_pct)}`}>
        {formatSignedPct(perf.portfolio_return_pct)}
      </span>
    ) : undefined;

  const pnl = portfolioSummary;
  const plainText = pnl ? plainTalk(holdings, pnl, t) : null;

  const attribution =
    perf && perf.attribution.length > 0
      ? perf.attribution.filter((a) => a.contribution_pct != null)
      : [];

  return (
    <>
      {pnl && pnl.hasQuotes && (
        <section className="flat-section cockpit-snapshot">
          <div className="cockpit-snapshot-head">
            <span className="flat-section-title">{t("center.focus")}</span>
            <span className="cockpit-snapshot-value mono">{formatSignedMoney(pnl.todayPnl)}</span>
          </div>
          <div className="cockpit-snapshot-metrics mono">
            <span className={`lists-portfolio-metric ${signedClass(pnl.todayPnl)}`}>
              <span className="lists-metric-label">{t("lists.todayPnl")}</span>
              <span>{formatSignedMoney(pnl.todayPnl)}</span>
            </span>
            <span className={`lists-portfolio-metric ${signedClass(pnl.todayPnlPct ?? 0)}`}>
              <span className="lists-metric-label">{t("lists.todayPnlPct")}</span>
              <span>{formatSignedPct(pnl.todayPnlPct)}</span>
            </span>
            <span className={`lists-portfolio-metric ${signedClass(pnl.totalProfit)}`}>
              <span className="lists-metric-label">{t("lists.totalPnl")}</span>
              <span>{formatSignedMoney(pnl.totalProfit)}</span>
            </span>
            <span className={`lists-portfolio-metric ${signedClass(pnl.totalProfitPct ?? 0)}`}>
              <span className="lists-metric-label">{t("lists.totalPnlPct")}</span>
              <span>{formatSignedPct(pnl.totalProfitPct)}</span>
            </span>
            <span className={`lists-portfolio-metric ${signedClass(pnl.annualizedPct ?? 0)}`}>
              <span className="lists-metric-label">{t("portfolio.annualized")}</span>
              <span>{pnl.annualizedPct != null ? formatSignedPct(pnl.annualizedPct) : "—"}</span>
            </span>
          </div>
          {plainText && (
            <p className="cockpit-plain-talk">
              <span className="lists-metric-label">{t("portfolio.plainToday")} · </span>
              {plainText}
            </p>
          )}
        </section>
      )}

      {perf && (
        <CollapsibleSection title={t("portfolio.perfTitle")} summary={perfSummary}>
          {perf.series.length > 0 ? (
            <div className="cockpit-perf-body">
              <CockpitPerfChart perf={perf} />
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

      {attribution.length > 0 && (
        <CollapsibleSection title={t("portfolio.attributionTitle")} defaultCollapsed>
          <p className="muted ledger-perf-basis">{t("portfolio.attributionHint")}</p>
          <table className="metrics-table cockpit-attribution">
            <thead>
              <tr>
                <th>{t("portfolio.tradeSymbol")}</th>
                <th>{t("portfolio.attributionReturn")}</th>
                <th>{t("portfolio.attributionWeight")}</th>
                <th>{t("portfolio.attributionContribution")}</th>
              </tr>
            </thead>
            <tbody>
              {attribution.map((a) => (
                <tr key={a.symbol}>
                  <td>{a.name}</td>
                  <td className={`mono ${signedClass(a.return_pct ?? 0)}`}>
                    {a.return_pct != null ? formatSignedPct(a.return_pct) : "—"}
                  </td>
                  <td className="mono">
                    {a.avg_weight_pct != null ? `${a.avg_weight_pct.toFixed(1)}%` : "—"}
                  </td>
                  <td className={`mono ${signedClass(a.contribution_pct ?? 0)}`}>
                    {a.contribution_pct != null ? `${a.contribution_pct.toFixed(2)}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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

      {timelines.length > 0 && (
        <CollapsibleSection title={t("portfolio.timelineTitle")} defaultCollapsed>
          <p className="muted ledger-perf-basis">{t("portfolio.timelineHint")}</p>
          <ul className="ledger-trades">
            {timelines.map((tl) => {
              const entry = tl.entries[0];
              const horizon = entry?.post_hoc?.[0];
              const bias = entry?.bias && BIAS_LABEL_KEYS[entry.bias] ? entry.bias : "neutral";
              return (
                <li key={tl.symbol} className="ledger-trade-row">
                  <span className="ledger-trade-name" title={tl.name}>
                    {tl.name}
                  </span>
                  <span className={`ledger-trade-bias ${bias}`}>{t(BIAS_LABEL_KEYS[bias])}</span>
                  {horizon && (
                    <span
                      className={`mono ledger-trade-pnl ${signedClass(horizon.return_pct ?? 0)}`}
                    >
                      {t("portfolio.timelinePostHoc", { days: String(horizon.days) })} ·{" "}
                      {horizon.return_pct != null ? formatSignedPct(horizon.return_pct) : "—"}
                    </span>
                  )}
                  <button
                    type="button"
                    className="example-chip"
                    onClick={() => onSelectLeader(tl.symbol, tl.name)}
                  >
                    {t("portfolio.timelineOpen")}
                  </button>
                </li>
              );
            })}
          </ul>
        </CollapsibleSection>
      )}

      <PortfolioEventsSection trigger={trigger} />

      <CounterfactualTeachingBlock holdings={holdings} trigger={trigger} />
    </>
  );
}
