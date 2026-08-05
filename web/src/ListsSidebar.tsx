import { useState, type ReactNode } from "react";
import type { HoldingEnriched, WatchlistItem, StockQuoteOut } from "./api";
import { HoldingTradeInlineRow } from "./HoldingTradeInlineRow";
import { ListsStockTable } from "./ListsStockTable";
import {
  formatMoney,
  formatPrice,
  formatSignedMoney,
  formatSignedPct,
  displayStockName,
  signedClass,
} from "./holdingDisplay";
import { useI18n } from "./i18n";
import type { ListsLayoutMode } from "./layoutTypes";
import { LISTS_DETAIL_WIDTH } from "./layoutSettings";
import type { PortfolioSummary, SectorWeight } from "./portfolioHelpers";
import { loadTheme } from "./themeSettings";
import { CollapsibleSection } from "./CollapsibleSection";
import { IconEdit, IconPlus } from "./ui/Icons";
import { WatchlistAddPanel } from "./WatchlistAddPanel";

const SECTOR_PALETTE_LIGHT = [
  "#3b9eff",
  "#f23645",
  "#00b386",
  "#c9a227",
  "#64748b",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
];
const SECTOR_PALETTE_DARK = [
  "#f04a3a",
  "#f23645",
  "#00b386",
  "#c9a227",
  "#64748b",
  "#ff6b52",
  "#ec4899",
  "#e6a817",
];

function sectorColor(sector: string): string {
  const theme = document.documentElement.dataset.theme ?? loadTheme();
  const palette = theme === "institutional-dark" ? SECTOR_PALETTE_DARK : SECTOR_PALETTE_LIGHT;
  let hash = 0;
  for (let i = 0; i < sector.length; i++) hash = (hash * 31 + sector.charCodeAt(i)) >>> 0;
  return palette[hash % palette.length];
}

function SectorDonut({ sectors }: { sectors: SectorWeight[] }) {
  const total = sectors.reduce((a, b) => a + b.pct, 0) || 1;
  const r = 36;
  const cx = 50;
  const cy = 50;
  const paths = sectors.reduce<{ nodes: ReactNode[]; acc: number }>(
    (state, s) => {
      const start = (state.acc / total) * Math.PI * 2 - Math.PI / 2;
      const nextAcc = state.acc + s.pct;
      const end = (nextAcc / total) * Math.PI * 2 - Math.PI / 2;
      const large = end - start > Math.PI ? 1 : 0;
      const x1 = cx + r * Math.cos(start);
      const y1 = cy + r * Math.sin(start);
      const x2 = cx + r * Math.cos(end);
      const y2 = cy + r * Math.sin(end);
      return {
        acc: nextAcc,
        nodes: [
          ...state.nodes,
          <path
            key={s.sector}
            d={`M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`}
            fill="none"
            stroke={sectorColor(s.sector)}
            strokeWidth="10"
          />,
        ],
      };
    },
    { nodes: [], acc: 0 },
  ).nodes;
  return (
    <svg className="lists-donut" viewBox="0 0 100 100" aria-hidden="true">
      {paths}
    </svg>
  );
}

interface ListsSidebarProps {
  mode: ListsLayoutMode;
  onSetMode: (mode: ListsLayoutMode) => void;
  onExpandLists: () => void;
  holdings: HoldingEnriched[];
  holdingsLoading: boolean;
  holdingsRefreshing?: boolean;
  portfolioSummary: PortfolioSummary;
  sectorMix: SectorWeight[];
  numLocale: string;
  selectedSymbol: string | null;
  onSelectHolding: (h: HoldingEnriched) => void;
  onAddHolding: () => void;
  onEditHolding: (h: HoldingEnriched) => void;
  onDeleteHolding: (id: number) => void;
  onTradeApplied: () => void | Promise<void>;
  inlineTradeOpen: boolean;
  onInlineTradeClose: () => void;
  watchlist: WatchlistItem[];
  watchlistQuotes: Record<string, StockQuoteOut>;
  watchlistLoading: boolean;
  onSelectWatchlist: (item: WatchlistItem) => void;
  onAddWatchlist: (symbol: string, name: string) => void | Promise<void>;
  onRemoveWatchlist: (id: number) => void;
  onBatchResearch: () => void;
  onListsResizeStart: () => void;
  listsWidth: number;
}

export function ListsSidebar({
  mode,
  onSetMode,
  onExpandLists,
  holdings,
  holdingsLoading,
  holdingsRefreshing = false,
  portfolioSummary,
  sectorMix,
  numLocale,
  selectedSymbol,
  onSelectHolding,
  onAddHolding,
  onEditHolding,
  onDeleteHolding,
  onTradeApplied,
  inlineTradeOpen,
  onInlineTradeClose,
  watchlist,
  watchlistQuotes,
  watchlistLoading,
  onSelectWatchlist,
  onAddWatchlist,
  onRemoveWatchlist,
  onBatchResearch,
  onListsResizeStart,
  listsWidth,
}: ListsSidebarProps) {
  const { t } = useI18n();
  const [holdingsEditMode, setHoldingsEditMode] = useState(false);
  const [watchlistEditMode, setWatchlistEditMode] = useState(false);
  const [watchlistAddOpen, setWatchlistAddOpen] = useState(false);
  const expanded = mode === "center";
  const listsDetail = expanded || listsWidth >= LISTS_DETAIL_WIDTH;
  const profitClass = signedClass(portfolioSummary.totalProfitPct);
  const todayClass = signedClass(portfolioSummary.todayPnlPct);

  return (
    <aside
      className={expanded ? "lists-column lists-column-center" : "lists-column"}
      aria-label={t("lists.aria")}
    >
      <div
        className="lists-resize-handle"
        role="separator"
        aria-orientation="vertical"
        aria-label={t("lists.resize")}
        onMouseDown={(e) => {
          e.preventDefault();
          onListsResizeStart();
        }}
      />
      <section className="flat-section lists-portfolio-summary">
        <div className="lists-portfolio-head">
          <div className="lists-portfolio-head-start">
            <div className="lists-portfolio-rail">
              <button
                type="button"
                className="rail-toggle"
                onClick={() => onSetMode("hidden")}
                title={t("lists.collapse")}
              >
                «
              </button>
              {mode === "sidebar" && (
                <button
                  type="button"
                  className="rail-toggle"
                  onClick={onExpandLists}
                  title={t("lists.expandCenter")}
                >
                  »
                </button>
              )}
              {mode === "center" && (
                <button
                  type="button"
                  className="rail-toggle"
                  onClick={() => onSetMode("sidebar")}
                  title={t("lists.restoreSidebar")}
                >
                  ‹
                </button>
              )}
            </div>
            <span className="flat-section-title">{t("lists.portfolio")}</span>
          </div>
          <span className="lists-portfolio-total mono">
            {portfolioSummary.hasQuotes ? formatMoney(portfolioSummary.totalValue, numLocale) : "—"}
          </span>
        </div>
        {portfolioSummary.hasQuotes &&
          (listsDetail ? (
            <div className="lists-portfolio-metrics-grid mono">
              <div className={`lists-portfolio-metric ${todayClass}`}>
                <span className="lists-metric-label">{t("lists.todayPnl")}</span>
                <span>{formatSignedMoney(portfolioSummary.todayPnl)}</span>
              </div>
              <div className={`lists-portfolio-metric ${profitClass}`}>
                <span className="lists-metric-label">{t("lists.totalPnl")}</span>
                <span>{formatSignedMoney(portfolioSummary.totalProfit)}</span>
              </div>
              <div className={`lists-portfolio-metric ${todayClass}`}>
                <span className="lists-metric-label">{t("lists.todayPnlPct")}</span>
                <span>{formatSignedPct(portfolioSummary.todayPnlPct)}</span>
              </div>
              <div className={`lists-portfolio-metric ${profitClass}`}>
                <span className="lists-metric-label">{t("lists.totalPnlPct")}</span>
                <span>{formatSignedPct(portfolioSummary.totalProfitPct)}</span>
              </div>
              <div
                className={`lists-portfolio-metric ${signedClass(portfolioSummary.annualizedPct)}`}
              >
                <span className="lists-metric-label">{t("portfolio.annualized")}</span>
                <span>
                  {portfolioSummary.annualizedPct != null
                    ? formatSignedPct(portfolioSummary.annualizedPct)
                    : "—"}
                </span>
              </div>
            </div>
          ) : (
            <div className={`lists-portfolio-pnl mono ${profitClass}`}>
              <span>{formatSignedMoney(portfolioSummary.totalProfit)}</span>
              <span className="lists-portfolio-pnl-sep" aria-hidden="true">
                ·
              </span>
              <span>{formatSignedPct(portfolioSummary.totalProfitPct)}</span>
              <span className="lists-portfolio-pnl-sep" aria-hidden="true">
                ·
              </span>
              <span className="lists-portfolio-pnl-annual">
                {t("portfolio.annualized")}{" "}
                {portfolioSummary.annualizedPct != null
                  ? formatSignedPct(portfolioSummary.annualizedPct)
                  : "—"}
              </span>
            </div>
          ))}
      </section>

      {sectorMix.length > 0 && (
        <CollapsibleSection title={t("lists.sectors")} defaultCollapsed>
          <div className={`lists-sector-panel${listsDetail ? " lists-sector-panel-detail" : ""}`}>
            <div className="lists-sector-visual">
              <SectorDonut sectors={sectorMix.slice(0, 6)} />
            </div>
            <div className="lists-sector-table-wrap">
              <table className="lists-sector-table mono">
                {listsDetail && (
                  <thead>
                    <tr>
                      <th className="lists-sector-col-name">{t("lists.sectors")}</th>
                      <th className="lists-sector-col-num lists-sector-col-pct">%</th>
                      <th className="lists-sector-col-num lists-sector-col-money">
                        {t("lists.colDailyPnl")}
                      </th>
                      <th className="lists-sector-col-num lists-sector-col-money">
                        {t("lists.colTotalPnl")}
                      </th>
                      <th className="lists-sector-col-num lists-sector-col-pct">
                        {t("lists.colAnnualized")}
                      </th>
                    </tr>
                  </thead>
                )}
                <tbody>
                  {sectorMix.map((s) => (
                    <tr key={s.sector}>
                      <td className="lists-sector-col-name">
                        <span
                          className="lists-sector-dot"
                          style={{ background: sectorColor(s.sector) }}
                        />
                        <span className="lists-sector-name">{s.sector}</span>
                      </td>
                      <td className="lists-sector-col-num lists-sector-col-pct">
                        {s.pct.toFixed(1)}%
                      </td>
                      {listsDetail ? (
                        <>
                          <td
                            className={`lists-sector-col-num lists-sector-col-money ${signedClass(s.todayPnl)}`}
                          >
                            {formatSignedMoney(s.todayPnl)}
                          </td>
                          <td
                            className={`lists-sector-col-num lists-sector-col-money ${signedClass(s.totalProfit)}`}
                          >
                            {formatSignedMoney(s.totalProfit)}
                          </td>
                          <td
                            className={`lists-sector-col-num lists-sector-col-pct ${signedClass(s.annualizedPct)}`}
                          >
                            {s.annualizedPct != null ? formatSignedPct(s.annualizedPct) : "—"}
                          </td>
                        </>
                      ) : (
                        <td
                          className={`lists-sector-col-num lists-sector-col-money ${signedClass(s.totalProfit)}`}
                        >
                          {formatSignedMoney(s.totalProfit)}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </CollapsibleSection>
      )}

      <section
        className={`flat-section lists-holdings-section${holdingsEditMode ? " lists-holdings-edit-mode" : ""}`}
      >
        <div className="lists-holdings-toolbar">
          <span className="flat-section-title">{t("lists.holdings")}</span>
          <div className="lists-holdings-toolbar-actions">
            <button
              type="button"
              className={`lists-ghost-icon${holdingsEditMode ? " active" : ""}`}
              onClick={() => setHoldingsEditMode((v) => !v)}
              title={holdingsEditMode ? t("portfolio.editDone") : t("portfolio.edit")}
              aria-label={holdingsEditMode ? t("portfolio.editDone") : t("portfolio.edit")}
              aria-pressed={holdingsEditMode}
            >
              <IconEdit size={14} />
            </button>
            <button
              type="button"
              className="lists-ghost-icon"
              onClick={onAddHolding}
              title={t("portfolio.tradeModalTitle")}
              aria-label={t("portfolio.tradeModalTitle")}
            >
              <IconPlus size={14} />
            </button>
          </div>
        </div>

        {holdingsLoading && holdings.length === 0 && (
          <p className="muted flat-empty">{t("lists.loading")}</p>
        )}
        {holdingsLoading && holdings.length > 0 && (
          <p className="muted lists-refresh-hint">{t("portfolio.quotesUpdating")}</p>
        )}
        {holdingsRefreshing && holdings.length > 0 && (
          <p className="muted lists-refresh-hint">{t("portfolio.quotesUpdating")}</p>
        )}
        {!holdingsLoading && holdings.length === 0 && !inlineTradeOpen && (
          <p className="muted flat-empty">{t("portfolio.empty")}</p>
        )}

        {listsDetail ? (
          <>
            {holdings.length > 0 && (
              <ListsStockTable
                kind="holding"
                holdings={holdings}
                selectedSymbol={selectedSymbol}
                onSelectHolding={onSelectHolding}
                editMode={holdingsEditMode}
                onEditHolding={onEditHolding}
                onDeleteHolding={onDeleteHolding}
                showHeaders
              />
            )}
            {inlineTradeOpen && (
              <HoldingTradeInlineRow
                holdings={holdings}
                onApplied={onTradeApplied}
                onCancel={onInlineTradeClose}
              />
            )}
          </>
        ) : (
          <ul className="lists-stock-list lists-holdings-list">
            {holdings.map((h) => (
              <li key={h.id ?? h.symbol} className="lists-holding-item">
                <button
                  type="button"
                  className={`lists-stock-row lists-holding-select${selectedSymbol === h.symbol ? " active" : ""}`}
                  onClick={() => onSelectHolding(h)}
                >
                  <span className="lists-stock-name" title={h.name}>
                    {displayStockName(h.symbol, h.name)}
                  </span>
                  <span className="mono lists-stock-meta">{h.symbol}</span>
                  <span className="mono lists-stock-price">
                    {h.price != null ? formatPrice(h.price) : "—"}
                  </span>
                  <span className={`mono ${signedClass(h.change_pct ?? 0)}`}>
                    {h.change_pct != null ? formatSignedPct(h.change_pct) : "—"}
                  </span>
                </button>
                {holdingsEditMode && h.id != null && (
                  <div className="lists-holding-actions">
                    <button
                      type="button"
                      className="lists-ghost-icon"
                      onClick={() => onEditHolding(h)}
                      title={t("portfolio.edit")}
                      aria-label={t("portfolio.edit")}
                    >
                      <IconEdit size={14} />
                    </button>
                    <button
                      type="button"
                      className="lists-ghost-icon lists-holding-delete"
                      onClick={() => onDeleteHolding(h.id!)}
                      title={t("portfolio.deleteHolding")}
                      aria-label={t("portfolio.deleteHolding")}
                    >
                      ×
                    </button>
                  </div>
                )}
              </li>
            ))}
            {inlineTradeOpen && (
              <HoldingTradeInlineRow
                holdings={holdings}
                onApplied={onTradeApplied}
                onCancel={onInlineTradeClose}
              />
            )}
          </ul>
        )}
      </section>

      <section
        className={`flat-section lists-watchlist-section${watchlistEditMode ? " lists-holdings-edit-mode" : ""} flat-section-last`}
      >
        <div className="lists-holdings-toolbar">
          <span className="flat-section-title">{t("lists.watchlist")}</span>
          <div className="lists-holdings-toolbar-actions">
            <button
              type="button"
              className={`lists-ghost-icon${watchlistEditMode ? " active" : ""}`}
              onClick={() => setWatchlistEditMode((v) => !v)}
              title={watchlistEditMode ? t("portfolio.editDone") : t("portfolio.edit")}
              aria-label={watchlistEditMode ? t("portfolio.editDone") : t("portfolio.edit")}
              aria-pressed={watchlistEditMode}
            >
              <IconEdit size={14} />
            </button>
            <button
              type="button"
              className="lists-ghost-icon"
              onClick={() => {
                setWatchlistAddOpen(true);
                setWatchlistEditMode(false);
              }}
              title={t("lists.watchlistAdd")}
              aria-label={t("lists.watchlistAdd")}
            >
              <IconPlus size={14} />
            </button>
            {watchlist.length > 0 && (
              <button
                type="button"
                className="example-chip lists-batch-research"
                onClick={onBatchResearch}
                title={t("lists.batchResearchTip")}
              >
                {t("lists.batchResearch")}
              </button>
            )}
          </div>
        </div>

        {watchlistLoading && watchlist.length === 0 && (
          <p className="muted flat-empty">{t("lists.loading")}</p>
        )}
        {!watchlistLoading && watchlist.length === 0 && !watchlistAddOpen && (
          <p className="muted flat-empty">{t("lists.watchlistEmpty")}</p>
        )}

        {listsDetail ? (
          watchlist.length > 0 && (
            <ListsStockTable
              kind="watchlist"
              watchlist={watchlist}
              watchlistQuotes={watchlistQuotes}
              selectedSymbol={selectedSymbol}
              onSelectWatchlist={onSelectWatchlist}
              editMode={watchlistEditMode}
              onDeleteWatchlist={onRemoveWatchlist}
              showHeaders
            />
          )
        ) : (
          <ul className="lists-stock-list lists-holdings-list">
            {watchlist.map((w) => {
              const q = watchlistQuotes[w.symbol];
              const label = displayStockName(w.symbol, w.name, q?.name);
              return (
                <li key={w.id} className="lists-holding-item">
                  <button
                    type="button"
                    className={`lists-stock-row lists-holding-select${selectedSymbol === w.symbol ? " active" : ""}`}
                    onClick={() => onSelectWatchlist(w)}
                  >
                    <span className="lists-stock-name" title={label}>
                      {label}
                    </span>
                    <span className="mono lists-stock-meta">{w.symbol}</span>
                    <span className="mono lists-stock-price">{q ? formatPrice(q.price) : "—"}</span>
                    <span className={`mono ${signedClass(q?.change_pct ?? 0)}`}>
                      {q ? formatSignedPct(q.change_pct) : "—"}
                    </span>
                  </button>
                  {watchlistEditMode && (
                    <div className="lists-holding-actions">
                      <button
                        type="button"
                        className="lists-ghost-icon lists-holding-delete"
                        onClick={() => onRemoveWatchlist(w.id)}
                        title={t("lists.watchlistRemove")}
                        aria-label={t("lists.watchlistRemove")}
                      >
                        ×
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        {watchlistAddOpen && (
          <WatchlistAddPanel
            onAdd={async (symbol, name) => {
              await onAddWatchlist(symbol, name);
              setWatchlistAddOpen(false);
            }}
            onCancel={() => setWatchlistAddOpen(false)}
          />
        )}
      </section>
    </aside>
  );
}
