import { useEffect, useMemo, useState } from "react";
import { api, type Briefing, type HoldingEnriched, type StockLookupOut } from "./api";
import { formatPrice, formatSignedMoney, formatSignedPct, signedClass } from "./holdingDisplay";
import { useI18n } from "./i18n";
import { localizeBriefing } from "./uiLabels";
import { StockChart } from "./StockChart";
import type { PortfolioSummary, SectorWeight } from "./portfolioHelpers";

interface PortfolioPanelProps {
  holdings: HoldingEnriched[];
  holdingsLoading: boolean;
  portfolioSummary: PortfolioSummary;
  sectorMix: SectorWeight[];
  numLocale: string;
  holdingInput: string;
  holdingCost: string;
  holdingLots: string;
  holdingDate: string;
  lookupResult: StockLookupOut | null;
  lookupPrice: number | null;
  lookupLoading: boolean;
  onHoldingInputChange: (value: string) => void;
  onHoldingCostChange: (value: string) => void;
  onHoldingLotsChange: (value: string) => void;
  onHoldingDateChange: (value: string) => void;
  onClearLookup: () => void;
  onLoadHoldings: () => void;
  onLookupAndAdd: () => void;
  onConfirmCandidate: (symbol: string, name: string) => void;
  onDeleteHolding: (id: number) => void;
  onAnalyzeHolding: (h: HoldingEnriched) => void;
  onAskCopilot?: (query: string) => void;
}

const SECTOR_PALETTE = ["#ff6600", "#00c853", "#4fc3f7", "#ffab00", "#8a8a8a", "#e91e63", "#9c27b0", "#795548"];

function sectorColor(sector: string): string {
  let hash = 0;
  for (let i = 0; i < sector.length; i++) {
    hash = (hash * 31 + sector.charCodeAt(i)) >>> 0;
  }
  return SECTOR_PALETTE[hash % SECTOR_PALETTE.length];
}

/** 根据 A 股交易时间返回当前简报类型 */
function getBriefingKind(): "morning" | "closing" {
  const now = new Date();
  const t = now.getHours() * 60 + now.getMinutes();
  // 09:30-15:00 为盘中 → closing kind (实时数据)
  if (t >= 570 && t < 900) return "closing";
  return "morning";
}

/** 根据 A 股交易时间返回简报标签 */
function briefingLabelByTime(): string {
  const now = new Date();
  const t = now.getHours() * 60 + now.getMinutes();
  if (t < 570) return "盘前简报";
  if (t < 690) return "盘中简报";
  if (t < 780) return "午间简报";
  if (t < 900) return "盘中简报";
  return "盘后简报";
}

function SectorDonut({ sectors }: { sectors: SectorWeight[] }) {
  const total = sectors.reduce((a, b) => a + b.pct, 0) || 1;
  let acc = 0;
  const r = 40;
  const cx = 50;
  const cy = 50;
  const paths = sectors.map((s) => {
    const start = (acc / total) * Math.PI * 2 - Math.PI / 2;
    acc += s.pct;
    const end = (acc / total) * Math.PI * 2 - Math.PI / 2;
    const large = end - start > Math.PI ? 1 : 0;
    const x1 = cx + r * Math.cos(start);
    const y1 = cy + r * Math.sin(start);
    const x2 = cx + r * Math.cos(end);
    const y2 = cy + r * Math.sin(end);
    return (
      <path
        key={s.sector}
        d={`M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`}
        fill="none"
        stroke={sectorColor(s.sector)}
        strokeWidth="12"
      />
    );
  });
  return (
    <svg className="donut" viewBox="0 0 100 100">
      {paths}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="12" />
    </svg>
  );
}

export function PortfolioPanel({
  holdings,
  holdingsLoading,
  portfolioSummary,
  sectorMix,
  numLocale,
  holdingInput,
  holdingCost,
  holdingLots,
  holdingDate,
  lookupResult,
  lookupPrice,
  lookupLoading,
  onHoldingInputChange,
  onHoldingCostChange,
  onHoldingLotsChange,
  onHoldingDateChange,
  onClearLookup,
  onLoadHoldings,
  onLookupAndAdd,
  onConfirmCandidate,
  onDeleteHolding,
  onAnalyzeHolding,
  onAskCopilot,
}: PortfolioPanelProps) {
  const { t } = useI18n();
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [autoBriefing, setAutoBriefing] = useState<boolean>(true);
  const [autoBriefingLoading, setAutoBriefingLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const [status, morning, closing] = await Promise.all([
          api.briefingSchedule(),
          api.latestBriefing("morning"),
          api.latestBriefing("closing"),
        ]);
        if (cancelled) return;
        setAutoBriefing(status.enabled);
        setBriefing(morning ?? closing ?? null);
      } catch {
        // ignore
      }
    }
    void init();
    return () => { cancelled = true; };
  }, []);

  async function loadBriefing(kind: "morning" | "closing") {
    setBriefingLoading(true);
    try {
      const b = await api.generateBriefing(kind);
      setBriefing(b);
    } finally {
      setBriefingLoading(false);
    }
  }

  async function toggleAutoBriefing() {
    const next = !autoBriefing;
    setAutoBriefingLoading(true);
    try {
      const status = await api.setBriefingSchedule(next);
      setAutoBriefing(status.enabled);
    } finally {
      setAutoBriefingLoading(false);
    }
  }

  const sectorPnl = useMemo(() => {
    const map = new Map<string, { pnl: number; value: number }>();
    for (const h of holdings) {
      if (!h.quote_available || h.price == null) continue;
      const sector = h.sector?.trim() || "未知";
      const mv = h.price * h.quantity;
      const entry = map.get(sector) ?? { pnl: 0, value: 0 };
      entry.pnl += h.profit_amount ?? 0;
      entry.value += mv;
      map.set(sector, entry);
    }
    return map;
  }, [holdings]);

  const briefingLabel = useMemo(() => briefingLabelByTime(), []);
  const briefingKind = useMemo(() => getBriefingKind(), []);
  const isTradingTime = briefingKind === "closing";
  const b = briefing ? localizeBriefing(briefing, t) : null;

  return (
    <div className="panel portfolio-panel">
      {/* 简报生成按钮 + 自动开关 */}
      <div className="panel-actions-row">
        <button
          className="btn btn-ghost btn-sm"
          disabled={briefingLoading}
          onClick={() => void loadBriefing(briefingKind)}
        >
          {briefingLoading
            ? t("portfolio.briefingLoading")
            : isTradingTime
              ? t("portfolio.briefingIntraday")
              : t("portfolio.briefingPostMarket")}
        </button>
        <label className="auto-briefing-toggle" title={t("portfolio.autoBriefingHint")}>
          <input
            type="checkbox"
            checked={autoBriefing}
            disabled={autoBriefingLoading}
            onChange={() => void toggleAutoBriefing()}
          />
          <span>{t("portfolio.autoBriefing")}</span>
        </label>
      </div>

      {/* 今日关注 · 简报卡片 */}
      {b && (
        <div className="briefing-card card card-accent">
          <div className="card-body">
            <div className="briefing-header">
              <span className="briefing-label">{briefingLabel}</span>
              <span className="briefing-date">{new Date().toLocaleDateString("zh-CN")}</span>
            </div>
            <p className="briefing-lead">{b.summary}</p>
            {b.sections.length > 0 && (
              <div className="briefing-vertical-list" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {b.sections.map((s) => (
                  <div key={s.title} className="briefing-point" style={{ display: "block", padding: "10px 12px", background: "var(--bbg-panel-2)", border: "1px solid var(--bbg-border)", borderLeft: "3px solid var(--bbg-orange)" }}>
                    <strong style={{ display: "block", fontSize: "11px", color: "var(--bbg-orange)", marginBottom: "4px", textTransform: "uppercase", letterSpacing: "0.06em" }}>{s.title}</strong>
                    <pre className="briefing-section" style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: "12px", margin: "4px 0 0", background: "transparent", border: "none", padding: "0" }}>{s.content}</pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 总持仓 + 行业分布 合并卡片 */}
      {holdings.length > 0 && sectorMix.length > 0 && (
        <div className="card portfolio-sector-card">
          <div className="card-body">
            <div className="portfolio-sector-grid">
              <div className="portfolio-vertical">
                <div className="summary-cell">
                  <span className="label">{t("portfolio.summaryValue")}</span>
                  <span className="value mono">
                    {portfolioSummary.hasQuotes
                      ? `¥${portfolioSummary.totalValue.toLocaleString(numLocale, { maximumFractionDigits: 0 })}`
                      : "—"}
                  </span>
                </div>
                <div className="summary-cell">
                  <span className="label">{t("portfolio.summaryToday")}</span>
                  <span className={`value mono ${signedClass(portfolioSummary.todayPnl)}`}>
                    {portfolioSummary.hasQuotes ? formatSignedMoney(portfolioSummary.todayPnl) : "—"}
                    {portfolioSummary.hasQuotes && (
                      <span className="today-pct">
                        {" "}
                        {formatSignedPct(
                          portfolioSummary.totalValue > 0
                            ? (portfolioSummary.todayPnl / portfolioSummary.totalValue) * 100
                            : 0
                        )}
                      </span>
                    )}
                  </span>
                </div>
                <div className="summary-cell">
                  <span className="label">{t("portfolio.summaryCount")}</span>
                  <span className="value small mono">{portfolioSummary.count}</span>
                </div>
              </div>
              <div className="sector-visual">
                <SectorDonut sectors={sectorMix} />
              </div>
              <div className="sector-detail-wrap">
                {sectorMix.map((s) => {
                  const pnl = sectorPnl.get(s.sector);
                  const color = sectorColor(s.sector);
                  return (
                    <div key={s.sector} className="sector-detail-item" style={{ borderLeftColor: color }}>
                      <div className="left">
                        <span className="dot" style={{ background: color }} />
                        <span className="name">{s.sector}</span>
                        <span className="pct">{s.pct.toFixed(0)}%</span>
                      </div>
                      <span className={`pnl ${signedClass(pnl?.pnl ?? 0)}`}>
                        {pnl ? formatSignedMoney(pnl.pnl) : "—"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 持仓状态栏 */}
      <div className="holding-toolbar">
        <span className="muted">
          {holdingsLoading
            ? t("portfolio.quotesUpdating")
            : holdings[0]?.market_session === "trading"
              ? t("portfolio.trading")
              : t("portfolio.closed")}
        </span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onLoadHoldings} disabled={holdingsLoading}>
          {t("portfolio.refresh")}
        </button>
      </div>

      {/* 持仓个股卡片网格 */}
      {holdings.length === 0 ? (
        <p className="muted holdings-empty">{t("portfolio.empty")}</p>
      ) : (
        <div className="holdings-grid">
          {holdings.map((h) => (
            <div key={h.id} className={`holding-card ${signedClass(h.profit_pct)}`}>
              <div className="holding-title">
                <div>
                  <div className="holding-name">{h.name}</div>
                  <div className="holding-symbol muted">
                    {h.symbol} · {h.sector}
                  </div>
                </div>
                {h.quote_available && h.change_pct != null && (
                  <span className={`holding-badge ${signedClass(h.change_pct)}`}>
                    {formatSignedPct(h.change_pct)}
                  </span>
                )}
              </div>
              <div className="holding-price mono">
                {h.quote_available ? formatPrice(h.price ?? null) : "—"}
              </div>
              <div className="holding-tags">
                <span className="holding-tag">{t("portfolio.qty")}: {h.quantity}</span>
                <span className="holding-tag">{t("portfolio.costCol")}: {h.cost_price.toFixed(2)}</span>
              </div>
              <div className="holding-pnl">
                <span className={`amt mono ${signedClass(h.profit_amount)}`}>
                  {h.quote_available ? formatSignedMoney(h.profit_amount ?? null) : "—"}
                </span>
                <span className={`pct mono ${signedClass(h.profit_pct)}`}>
                  {h.quote_available ? formatSignedPct(h.profit_pct ?? null) : "—"}
                </span>
              </div>
              <div className="holding-actions">
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => onAnalyzeHolding(h)}>
                  {t("portfolio.analyze")}
                </button>
                <button
                  type="button"
                  className={`btn btn-ghost btn-sm${chartSymbol === h.symbol ? " active" : ""}`}
                  onClick={() => setChartSymbol(chartSymbol === h.symbol ? null : h.symbol)}
                >
                  {t("portfolio.chart")}
                </button>
                <button type="button" className="delete-btn" onClick={() => h.id && onDeleteHolding(h.id)}>
                  DEL
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {chartSymbol && (
        <div className="portfolio-chart-panel">
          <StockChart symbol={chartSymbol} />
        </div>
      )}

      {/* 添加持仓表单 */}
      <div className="portfolio-add-footer">
        <div className="holding-form">
          <div className="field">
            <span className="field-label">{t("portfolio.symbol")}</span>
            <input
              placeholder={t("portfolio.symbolPh")}
              value={holdingInput}
              onChange={(e) => {
                onHoldingInputChange(e.target.value);
                onClearLookup();
              }}
              onKeyDown={(e) => e.key === "Enter" && onLookupAndAdd()}
            />
          </div>
          <div className="field">
            <span className="field-label">{t("portfolio.cost")}</span>
            <input type="number" placeholder="0.00" value={holdingCost} onChange={(e) => onHoldingCostChange(e.target.value)} />
          </div>
          <div className="field">
            <span className="field-label">{t("portfolio.lots")}</span>
            <input type="number" placeholder="1" value={holdingLots} onChange={(e) => onHoldingLotsChange(e.target.value)} />
          </div>
          <div className="field">
            <span className="field-label">{t("portfolio.buyDate")}</span>
            <input
              type="date"
              value={holdingDate}
              max={new Date().toISOString().slice(0, 10)}
              title={t("portfolio.buyDateTitle")}
              onChange={(e) => onHoldingDateChange(e.target.value)}
            />
          </div>
          <button className="btn btn-primary" onClick={onLookupAndAdd} disabled={lookupLoading} style={{ alignSelf: "end" }}>
            {lookupLoading ? t("portfolio.querying") : t("portfolio.add")}
          </button>
        </div>
        {lookupResult && lookupResult.status === "ambiguous" && (
          <div className="confirm-card">
            <span className="field-label">{t("portfolio.pickStock")}</span>
            <div className="candidate-list">
              {lookupResult.candidates.map((c) => (
                <button key={c.symbol} className="btn btn-ghost" onClick={() => onConfirmCandidate(c.symbol, c.name)}>
                  {c.name} ({c.symbol})
                </button>
              ))}
            </div>
          </div>
        )}
        {lookupResult?.status === "confirmed" && lookupPrice != null && (
          <p className="lookup-price-ref">
            {t("portfolio.lookupPrice")}: {formatPrice(lookupPrice)}
          </p>
        )}
      </div>

      {/* 底部 AI 对话入口 */}
      {onAskCopilot && holdings.length > 0 && (
        <div className="ai-bottom-entry">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => onAskCopilot(t("portfolio.askPnl"))}
          >
            {t("portfolio.askPnl")}
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => onAskCopilot(t("portfolio.askTopMover"))}
          >
            {t("portfolio.askTopMover")}
          </button>
          <button
            type="button"
            className="btn btn-primary ai-chat-trigger"
            onClick={() => onAskCopilot("")}
          >
            {t("portfolio.aiChatEntry")}
          </button>
        </div>
      )}
    </div>
  );
}
