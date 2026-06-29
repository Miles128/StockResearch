import { useState } from "react";
import type { HoldingEnriched, WatchlistItem, StockQuoteOut } from "./api";
import { formatMoney, formatSignedMoney, formatSignedPct, signedClass } from "./holdingDisplay";
import { useI18n } from "./i18n";
import type { ListsLayoutMode } from "./layoutTypes";
import type { PortfolioSummary, SectorWeight } from "./portfolioHelpers";
import { loadTheme } from "./themeSettings";
import { CollapsibleSection } from "./CollapsibleSection";
import { IconPlus } from "./ui/Icons";

const SECTOR_PALETTE_LIGHT = ["#3b9eff", "#f23645", "#00b386", "#c9a227", "#64748b", "#8b5cf6", "#ec4899", "#14b8a6"];
const SECTOR_PALETTE_DARK = ["#f04a3a", "#f23645", "#00b386", "#c9a227", "#64748b", "#ff6b52", "#ec4899", "#e6a817"];

function sectorColor(sector: string): string {
  const theme = document.documentElement.dataset.theme ?? loadTheme();
  const palette = theme === "institutional-dark" ? SECTOR_PALETTE_DARK : SECTOR_PALETTE_LIGHT;
  let hash = 0;
  for (let i = 0; i < sector.length; i++) hash = (hash * 31 + sector.charCodeAt(i)) >>> 0;
  return palette[hash % palette.length];
}

function SectorDonut({ sectors }: { sectors: SectorWeight[] }) {
  const total = sectors.reduce((a, b) => a + b.pct, 0) || 1;
  let acc = 0;
  const r = 36;
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
        strokeWidth="10"
      />
    );
  });
  return (
    <svg className="lists-donut" viewBox="0 0 100 100" aria-hidden="true">
      {paths}
    </svg>
  );
}

interface ListsSidebarProps {
  mode: ListsLayoutMode;
  onSetMode: (mode: ListsLayoutMode) => void;
  holdings: HoldingEnriched[];
  holdingsLoading: boolean;
  portfolioSummary: PortfolioSummary;
  sectorMix: SectorWeight[];
  numLocale: string;
  selectedSymbol: string | null;
  onSelectHolding: (h: HoldingEnriched) => void;
  watchlist: WatchlistItem[];
  watchlistQuotes: Record<string, StockQuoteOut>;
  watchlistLoading: boolean;
  onSelectWatchlist: (item: WatchlistItem) => void;
  onAddWatchlist: (query: string) => void;
  onRemoveWatchlist: (id: number) => void;
}

export function ListsSidebar({
  mode,
  onSetMode,
  holdings,
  holdingsLoading,
  portfolioSummary,
  sectorMix,
  numLocale,
  selectedSymbol,
  onSelectHolding,
  watchlist,
  watchlistQuotes,
  watchlistLoading,
  onSelectWatchlist,
  onAddWatchlist,
  onRemoveWatchlist,
}: ListsSidebarProps) {
  const { t } = useI18n();
  const [addQuery, setAddQuery] = useState("");

  const todayPct =
    portfolioSummary.totalValue > 0
      ? (portfolioSummary.todayPnl / portfolioSummary.totalValue) * 100
      : 0;
  const todayClass = signedClass(todayPct);

  return (
    <aside className={mode === "center" ? "lists-column lists-column-center" : "lists-column"} aria-label={t("lists.aria")}>
      <section className="flat-section">
        <div className="section-title-row">
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
              onClick={() => onSetMode("center")}
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
          <span className="flat-section-title">{t("lists.portfolio")}</span>
        </div>
        <div className="flat-metric mono">{formatMoney(portfolioSummary.totalValue, numLocale)}</div>
        <div className={`flat-sub mono ${todayClass}`}>
          {formatSignedMoney(portfolioSummary.todayPnl)} {formatSignedPct(todayPct)}
        </div>
      </section>

      {sectorMix.length > 0 && (
        <CollapsibleSection title={t("lists.sectors")}>
          <div className="lists-sector-row">
            <SectorDonut sectors={sectorMix.slice(0, 6)} />
            <ul className="lists-sector-legend">
              {sectorMix.slice(0, 5).map((s) => (
                <li key={s.sector}>
                  <span className="lists-sector-dot" style={{ background: sectorColor(s.sector) }} />
                  <span>{s.sector}</span>
                  <span className="mono">{s.pct.toFixed(1)}%</span>
                </li>
              ))}
            </ul>
          </div>
        </CollapsibleSection>
      )}

      <CollapsibleSection title={t("lists.holdings")}>
        {holdingsLoading && <p className="muted flat-empty">{t("lists.loading")}</p>}
        {!holdingsLoading && holdings.length === 0 && (
          <p className="muted flat-empty">{t("portfolio.empty")}</p>
        )}
        <ul className="lists-stock-list">
          {holdings.map((h) => (
            <li key={h.id ?? h.symbol}>
              <button
                type="button"
                className={`lists-stock-row${selectedSymbol === h.symbol ? " active" : ""}`}
                onClick={() => onSelectHolding(h)}
              >
                <span className="lists-stock-name">{h.name}</span>
                <span className="mono lists-stock-meta">{h.symbol}</span>
                <span className={`mono ${signedClass(h.change_pct ?? 0)}`}>
                  {h.change_pct != null ? formatSignedPct(h.change_pct) : "—"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </CollapsibleSection>

      <CollapsibleSection title={t("lists.watchlist")} className="flat-section-last">
        {watchlistLoading && <p className="muted flat-empty">{t("lists.loading")}</p>}
        {!watchlistLoading && watchlist.length === 0 && (
          <p className="muted flat-empty">{t("lists.watchlistEmpty")}</p>
        )}
        <ul className="lists-stock-list">
          {watchlist.map((w) => {
            const q = watchlistQuotes[w.symbol];
            return (
              <li key={w.id}>
                <button
                  type="button"
                  className={`lists-stock-row${selectedSymbol === w.symbol ? " active" : ""}`}
                  onClick={() => onSelectWatchlist(w)}
                >
                  <span className="lists-stock-name">{w.name}</span>
                  <span className="mono lists-stock-meta">{w.symbol}</span>
                  <span className={`mono ${signedClass(q?.change_pct ?? 0)}`}>
                    {q ? formatSignedPct(q.change_pct) : "—"}
                  </span>
                </button>
                <button
                  type="button"
                  className="lists-watchlist-remove icon-btn"
                  onClick={() => onRemoveWatchlist(w.id)}
                  title={t("lists.watchlistRemove")}
                >
                  ×
                </button>
              </li>
            );
          })}
        </ul>
        <form
          className="lists-watchlist-add"
          onSubmit={(e) => {
            e.preventDefault();
            if (addQuery.trim()) {
              onAddWatchlist(addQuery.trim());
              setAddQuery("");
            }
          }}
        >
          <input
            value={addQuery}
            onChange={(e) => setAddQuery(e.target.value)}
            placeholder={t("lists.watchlistAddPh")}
          />
          <button type="submit" className="icon-btn lists-watchlist-add-btn" title={t("lists.watchlistAdd")} aria-label={t("lists.watchlistAdd")}>
            <IconPlus />
          </button>
        </form>
      </CollapsibleSection>
    </aside>
  );
}
