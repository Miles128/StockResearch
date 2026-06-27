import { useMemo, useState } from "react";
import { type HoldingEnriched } from "./api";
import { formatMoney, formatPrice, formatSignedMoney, formatSignedPct, signedClass } from "./holdingDisplay";
import type { HoldingsView } from "./modeSettings";
import { HoldingTradeModal } from "./HoldingTradeModal";
import { getBriefingKind } from "./briefingKind";
import { useI18n } from "./i18n";
import { StockChart } from "./StockChart";
import type { PortfolioSummary, SectorWeight } from "./portfolioHelpers";

interface PortfolioPanelProps {
  holdings: HoldingEnriched[];
  holdingsLoading: boolean;
  portfolioSummary: PortfolioSummary;
  sectorMix: SectorWeight[];
  numLocale: string;
  holdingsView?: HoldingsView;
  chatLoading?: boolean;
  onLoadHoldings: () => void;
  onDeleteHolding: (id: number) => void;
  onAnalyzeHolding: (h: HoldingEnriched) => void;
  onAskCopilot?: (query: string, options?: { briefingKind?: "intraday" | "postmarket" }) => void;
}

const SECTOR_PALETTE = ["#ff6600", "#00c853", "#4fc3f7", "#ffab00", "#8a8a8a", "#e91e63", "#9c27b0", "#795548"];

function sectorColor(sector: string): string {
  let hash = 0;
  for (let i = 0; i < sector.length; i++) {
    hash = (hash * 31 + sector.charCodeAt(i)) >>> 0;
  }
  return SECTOR_PALETTE[hash % SECTOR_PALETTE.length];
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
  holdingsView = "table",
  chatLoading = false,
  onLoadHoldings,
  onDeleteHolding,
  onAnalyzeHolding,
  onAskCopilot,
}: PortfolioPanelProps) {
  const { t } = useI18n();
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [tradeModalOpen, setTradeModalOpen] = useState(false);

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

  const briefingKind = useMemo(() => getBriefingKind(), []);
  const briefingQuery =
    briefingKind === "intraday" ? t("portfolio.briefingIntraday") : t("portfolio.briefingPostMarket");

  function holdingMarketValue(h: HoldingEnriched): number | null {
    if (!h.quote_available || h.price == null) return null;
    return h.price * h.quantity;
  }

  function holdingWeight(mv: number | null): number | null {
    if (mv == null || portfolioSummary.totalValue <= 0) return null;
    return (mv / portfolioSummary.totalValue) * 100;
  }

  function renderHoldingsTable() {
    return (
      <div className="holdings-table-wrap">
        <table className="holdings-table">
          <thead>
            <tr>
              <th>{t("portfolio.stock")}</th>
              <th className="num">{t("portfolio.marketValueCol")}</th>
              <th className="num">{t("portfolio.weightCol")}</th>
              <th className="num">{t("portfolio.latestPriceCol")}</th>
              <th className="num">{t("portfolio.dayChangeCol")}</th>
              <th className="num">{t("portfolio.totalPnlCol")}</th>
              <th className="num">{t("portfolio.totalPnlPctCol")}</th>
              <th className="actions">{t("portfolio.actionsCol")}</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => {
              const mv = holdingMarketValue(h);
              const weight = holdingWeight(mv);
              return (
                <tr key={h.id}>
                  <td>
                    <div className="holding-name">{h.name}</div>
                    <div className="holding-meta muted">
                      {h.symbol} · {h.sector}
                    </div>
                  </td>
                  <td className="mono num">{h.quote_available ? formatMoney(mv, numLocale) : "—"}</td>
                  <td className="mono num">{weight != null ? `${weight.toFixed(1)}%` : "—"}</td>
                  <td className="mono num">
                    {h.quote_available ? formatPrice(h.price ?? null) : "—"}
                  </td>
                  <td className={`mono num ${signedClass(h.change_pct)}`}>
                    {h.quote_available ? formatSignedPct(h.change_pct ?? null) : "—"}
                  </td>
                  <td className={`mono num ${signedClass(h.profit_amount)}`}>
                    {h.quote_available ? formatSignedMoney(h.profit_amount ?? null) : "—"}
                  </td>
                  <td className={`mono num ${signedClass(h.profit_pct)}`}>
                    {h.quote_available ? formatSignedPct(h.profit_pct ?? null) : "—"}
                  </td>
                  <td className="actions">
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => onAnalyzeHolding(h)}>
                      {t("portfolio.analyze")}
                    </button>{" "}
                    <button
                      type="button"
                      className={`btn btn-ghost btn-sm${chartSymbol === h.symbol ? " active" : ""}`}
                      onClick={() => setChartSymbol(chartSymbol === h.symbol ? null : h.symbol)}
                    >
                      {t("portfolio.chart")}
                    </button>
                    {editMode && h.id != null ? (
                      <>
                        {" "}
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm holding-delete-btn"
                          onClick={() => onDeleteHolding(h.id!)}
                        >
                          {t("portfolio.deleteHolding")}
                        </button>
                      </>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }

  function renderHoldingsCards() {
    return (
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
              <span className="holding-tag">
                {t("portfolio.marketValueCol")}:{" "}
                {h.quote_available ? formatMoney(holdingMarketValue(h), numLocale) : "—"}
              </span>
              <span className="holding-tag">
                {t("portfolio.weightCol")}:{" "}
                {holdingWeight(holdingMarketValue(h)) != null
                  ? `${holdingWeight(holdingMarketValue(h))!.toFixed(1)}%`
                  : "—"}
              </span>
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
    );
  }

  return (
    <div className="panel portfolio-panel">
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
          ) : holdingsView === "table" ? (
            renderHoldingsTable()
          ) : (
            renderHoldingsCards()
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
            disabled={chatLoading}
            onClick={() => onAskCopilot(briefingQuery, { briefingKind })}
          >
            {chatLoading ? t("portfolio.briefingLoading") : briefingQuery}
          </button>
          {holdings.length > 0 && (
            <>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={chatLoading}
                onClick={() => onAskCopilot(t("portfolio.askPnl"))}
              >
                {t("portfolio.askPnl")}
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={chatLoading}
                onClick={() => onAskCopilot(t("portfolio.askTopMover"))}
              >
                {t("portfolio.askTopMover")}
              </button>
            </>
          )}
          <button
            type="button"
            className="btn btn-primary ai-chat-trigger"
            disabled={chatLoading}
            onClick={() => onAskCopilot("")}
          >
            {t("portfolio.aiChatEntry")}
          </button>
        </div>
      )}
    </div>
  );
}
