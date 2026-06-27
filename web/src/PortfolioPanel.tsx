import { useEffect, useMemo, useState } from "react";
import { api, type Briefing, type HoldingEnriched } from "./api";
import { formatPrice, formatSignedMoney, formatSignedPct, signedClass } from "./holdingDisplay";
import { HoldingTradeModal } from "./HoldingTradeModal";
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
  onLoadHoldings: () => void;
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
  onLoadHoldings,
  onDeleteHolding,
  onAnalyzeHolding,
  onAskCopilot,
}: PortfolioPanelProps) {
  const { t } = useI18n();
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [tradeModalOpen, setTradeModalOpen] = useState(false);
  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const [morning, closing] = await Promise.all([
          api.latestBriefing("morning"),
          api.latestBriefing("closing"),
        ]);
        if (cancelled) return;
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
      {/* 今日关注 · 简报卡片 */}
      {b && (
        <div className="card portfolio-block">
          <div className="card-header">
            <span className="card-header-title">{briefingLabel}</span>
            <span className="card-header-meta">{new Date().toLocaleDateString("zh-CN")}</span>
          </div>
          <div className="card-body">
            <p className="briefing-lead">{b.summary}</p>
            {b.sections.length > 0 && (
              <div className="briefing-vertical-list">
                {b.sections.map((s) => (
                  <div key={s.title} className="briefing-point">
                    <strong>{s.title}</strong>
                    <pre className="briefing-section">{s.content}</pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 总持仓 + 行业分布 */}
      {holdings.length > 0 && sectorMix.length > 0 && (
        <div className="card portfolio-block portfolio-sector-card">
          <div className="card-header">
            <span className="card-header-title">{t("portfolio.overviewTitle")}</span>
          </div>
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
                    <div key={s.sector} className="sector-detail-item">
                      <div className="left">
                        <span className="dot" style={{ background: color }} />
                        <span className="name">{s.sector}</span>
                        <span className="pct">
                          {s.pct.toFixed(0)}% · {t("portfolio.sectorStockCount", { n: String(s.count) })}
                        </span>
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

      {/* 持仓个股 */}
      <div className="card portfolio-block">
        <div className="card-header">
          <span className="card-header-title">{t("portfolio.holdingsTitle")}</span>
          <div className="card-header-meta card-header-actions">
            <span className="muted">
              {holdingsLoading
                ? t("portfolio.quotesUpdating")
                : holdings[0]?.market_session === "trading"
                  ? t("portfolio.trading")
                  : holdings.length > 0
                    ? t("portfolio.closed")
                    : null}
            </span>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onLoadHoldings} disabled={holdingsLoading}>
              {t("portfolio.refresh")}
            </button>
            <button
              type="button"
              className={`btn btn-ghost btn-sm${editMode ? " active" : ""}`}
              onClick={() => setEditMode((v) => !v)}
            >
              {editMode ? t("portfolio.editDone") : t("portfolio.edit")}
            </button>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => setTradeModalOpen(true)}>
              {t("portfolio.add")}
            </button>
          </div>
        </div>
        <div className="card-body">
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
                    <div className="holding-title-actions">
                      {h.quote_available && h.change_pct != null && (
                        <span className={`holding-badge ${signedClass(h.change_pct)}`}>
                          {formatSignedPct(h.change_pct)}
                        </span>
                      )}
                      {editMode && h.id != null && (
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm holding-delete-btn"
                          onClick={() => onDeleteHolding(h.id!)}
                        >
                          {t("portfolio.deleteHolding")}
                        </button>
                      )}
                    </div>
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
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <HoldingTradeModal
        open={tradeModalOpen}
        holdings={holdings}
        onClose={() => setTradeModalOpen(false)}
        onApplied={onLoadHoldings}
      />

      {chartSymbol && (
        <div className="portfolio-chart-panel">
          <StockChart symbol={chartSymbol} />
        </div>
      )}

      {/* 底部 AI 对话入口 */}
      {onAskCopilot && (
        <div className="ai-bottom-entry">
          <button
            type="button"
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
          {holdings.length > 0 && (
            <>
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
            </>
          )}
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
