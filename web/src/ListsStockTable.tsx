import type { HoldingEnriched, StockQuoteOut, WatchlistItem } from "./api";
import {
  computeDailyPnlAmount,
  displayStockName,
  formatHoldingDuration,
  formatPrice,
  formatSignedMoney,
  formatSignedPct,
  signedClass,
} from "./holdingDisplay";
import { useI18n } from "./i18n";

type StockRowKind = "holding" | "watchlist";

interface ListsStockTableProps {
  kind: StockRowKind;
  holdings?: HoldingEnriched[];
  watchlist?: WatchlistItem[];
  watchlistQuotes?: Record<string, StockQuoteOut>;
  selectedSymbol: string | null;
  onSelectHolding?: (h: HoldingEnriched) => void;
  onSelectWatchlist?: (item: WatchlistItem) => void;
  editMode?: boolean;
  onEditHolding?: (h: HoldingEnriched) => void;
  onDeleteHolding?: (id: number) => void;
  onDeleteWatchlist?: (id: number) => void;
  /** Table column headers — hidden in narrow sidebar. */
  showHeaders?: boolean;
}

function openPrice(h: HoldingEnriched): number | null {
  if (h.open != null && h.open > 0) return h.open;
  return null;
}

function quoteOpen(q: StockQuoteOut | undefined): number | null {
  if (q?.open != null && q.open > 0) return q.open;
  return null;
}

export function ListsStockTable({
  kind,
  holdings = [],
  watchlist = [],
  watchlistQuotes = {},
  selectedSymbol,
  onSelectHolding,
  onSelectWatchlist,
  editMode = false,
  onEditHolding,
  onDeleteHolding,
  onDeleteWatchlist,
  showHeaders = false,
}: ListsStockTableProps) {
  const { t } = useI18n();

  const rows =
    kind === "holding"
      ? holdings.map((h) => ({
          key: String(h.id ?? h.symbol),
          symbol: h.symbol,
          name: displayStockName(h.symbol, h.name),
          price: h.price,
          open: openPrice(h),
          changePct: h.change_pct,
          quantity: h.quantity,
          cost: h.cost_price,
          buyDate: h.buy_date,
          profitAmount: h.profit_amount,
          profitPct: h.profit_pct,
          annualizedPct: h.annualized_pct,
          quoteAvailable: h.quote_available,
          holding: h,
          watchItem: null as WatchlistItem | null,
        }))
      : watchlist.map((w) => {
          const q = watchlistQuotes[w.symbol];
          return {
            key: String(w.id),
            symbol: w.symbol,
            name: displayStockName(w.symbol, w.name, q?.name),
            price: q?.price ?? null,
            open: quoteOpen(q),
            changePct: q?.change_pct ?? null,
            quantity: 0,
            cost: null as number | null,
            buyDate: null as string | null | undefined,
            profitAmount: null as number | null,
            profitPct: null as number | null,
            annualizedPct: null as number | null,
            quoteAvailable: q != null,
            holding: null as HoldingEnriched | null,
            watchItem: w,
          };
        });

  return (
    <div className="lists-detail-table-wrap">
      <table className="lists-detail-table">
        {showHeaders && (
          <thead>
            <tr>
              <th className="lists-col-symbol">{t("lists.colSymbol")}</th>
              <th className="lists-col-name">{t("lists.colName")}</th>
              <th className="lists-col-price">{t("lists.colPrice")}</th>
              <th className="lists-col-price">{t("lists.colOpen")}</th>
              <th className="lists-col-money">{t("lists.colDailyPnl")}</th>
              <th className="lists-col-pct">{t("lists.colDailyPct")}</th>
              {kind === "holding" && (
                <>
                  <th className="lists-col-price">{t("lists.colCost")}</th>
                  <th className="lists-col-days">{t("lists.colHoldDays")}</th>
                </>
              )}
              <th className="lists-col-money">{t("lists.colTotalPnl")}</th>
              <th className="lists-col-pct">{t("lists.colTotalPct")}</th>
              <th className="lists-col-pct">{t("lists.colAnnualized")}</th>
              {editMode && (kind === "holding" || kind === "watchlist") && (
                <th
                  className="lists-col-actions"
                  aria-label={kind === "holding" ? t("portfolio.edit") : t("lists.watchlistRemove")}
                />
              )}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row) => {
            const dailyPnl = computeDailyPnlAmount(row.price, row.quantity, row.changePct);
            const active = selectedSymbol === row.symbol;
            return (
              <tr
                key={row.key}
                className={`lists-detail-row${active ? " active" : ""}`}
                onClick={() => {
                  if (row.holding && onSelectHolding) onSelectHolding(row.holding);
                  if (row.watchItem && onSelectWatchlist) onSelectWatchlist(row.watchItem);
                }}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key !== "Enter" && e.key !== " ") return;
                  e.preventDefault();
                  if (row.holding && onSelectHolding) onSelectHolding(row.holding);
                  if (row.watchItem && onSelectWatchlist) onSelectWatchlist(row.watchItem);
                }}
              >
                <td className="mono lists-col-symbol">{row.symbol}</td>
                <td className="lists-detail-name lists-col-name" title={row.name}>
                  {row.name}
                </td>
                <td className="mono lists-col-price">
                  {row.quoteAvailable ? formatPrice(row.price) : "—"}
                </td>
                <td className="mono lists-col-price">
                  {row.open != null ? formatPrice(row.open) : "—"}
                </td>
                <td className={`mono lists-col-money ${signedClass(dailyPnl)}`}>
                  {row.quoteAvailable && dailyPnl != null ? formatSignedMoney(dailyPnl) : "—"}
                </td>
                <td className={`mono lists-col-pct ${signedClass(row.changePct)}`}>
                  {row.quoteAvailable && row.changePct != null ? formatSignedPct(row.changePct) : "—"}
                </td>
                {kind === "holding" && (
                  <>
                    <td className="mono lists-col-price">{formatPrice(row.cost ?? undefined)}</td>
                    <td className="mono lists-col-days">{formatHoldingDuration(row.buyDate)}</td>
                  </>
                )}
                <td className={`mono lists-col-money ${signedClass(row.profitAmount)}`}>
                  {row.quoteAvailable && row.profitAmount != null
                    ? formatSignedMoney(row.profitAmount)
                    : "—"}
                </td>
                <td className={`mono lists-col-pct ${signedClass(row.profitPct)}`}>
                  {row.quoteAvailable && row.profitPct != null ? formatSignedPct(row.profitPct) : "—"}
                </td>
                <td className={`mono lists-col-pct ${signedClass(row.annualizedPct)}`}>
                  {row.quoteAvailable && row.annualizedPct != null
                    ? formatSignedPct(row.annualizedPct)
                    : "—"}
                </td>
                {editMode && kind === "holding" && row.holding?.id != null && (
                  <td className="lists-detail-actions lists-col-actions" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      className="lists-ghost-icon"
                      onClick={() => onEditHolding?.(row.holding!)}
                      title={t("portfolio.edit")}
                    >
                      ✎
                    </button>
                    <button
                      type="button"
                      className="lists-ghost-icon lists-holding-delete"
                      onClick={() => onDeleteHolding?.(row.holding!.id!)}
                      title={t("portfolio.deleteHolding")}
                    >
                      ×
                    </button>
                  </td>
                )}
                {editMode && kind === "watchlist" && row.watchItem != null && (
                  <td className="lists-detail-actions lists-col-actions" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      className="lists-ghost-icon lists-holding-delete"
                      onClick={() => onDeleteWatchlist?.(row.watchItem!.id)}
                      title={t("lists.watchlistRemove")}
                    >
                      ×
                    </button>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
