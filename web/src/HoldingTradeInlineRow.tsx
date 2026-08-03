import { useState } from "react";
import { api, type HoldingEnriched, type HoldingTransactionItem } from "./api";
import { useI18n } from "./i18n";

const LOTS_SIZE = 100;

interface HoldingTradeInlineRowProps {
  holdings: HoldingEnriched[];
  onApplied: () => void | Promise<void>;
  onCancel: () => void;
}

function validateSellQuantities(
  transactions: HoldingTransactionItem[],
  holdings: HoldingEnriched[],
  t: (key: string) => string,
): string | null {
  const available = new Map(holdings.map((h) => [h.symbol, h.quantity]));
  for (const tx of transactions) {
    if (tx.side !== "sell" || !tx.symbol) continue;
    const qty = tx.lots * LOTS_SIZE;
    const left = available.get(tx.symbol) ?? 0;
    if (qty > left) {
      const label = tx.name || tx.symbol;
      return t("portfolio.tradeSellExceeds")
        .replace("{name}", label)
        .replace("{n}", String(left));
    }
    available.set(tx.symbol, left - qty);
  }
  return null;
}

async function buildPayload(
  side: "buy" | "sell",
  query: string,
  costPrice: string,
  lots: string,
  tradeDate: string,
): Promise<HoldingTransactionItem> {
  const parsedLots = parseInt(lots, 10);
  let symbol: string | undefined;
  let name: string | undefined;
  let lookupQuery = query.trim() || undefined;

  if (query.trim()) {
    const lookup = await api.lookupStock(query.trim());
    if (lookup.status === "ambiguous") {
      throw new Error(lookup.message || query);
    }
    if (lookup.status !== "confirmed" || !lookup.symbol || !lookup.name) {
      throw new Error(lookup.message || query);
    }
    symbol = lookup.symbol;
    name = lookup.name;
    lookupQuery = undefined;
  }

  return {
    side,
    symbol,
    name,
    query: lookupQuery,
    lots: parsedLots,
    cost_price: side === "buy" ? parseFloat(costPrice) : undefined,
    trade_date: side === "buy" ? tradeDate : undefined,
  };
}

export function HoldingTradeInlineRow({
  holdings,
  onApplied,
  onCancel,
}: HoldingTradeInlineRowProps) {
  const { t } = useI18n();
  const today = new Date().toISOString().slice(0, 10);
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [query, setQuery] = useState("");
  const [costPrice, setCostPrice] = useState("");
  const [lots, setLots] = useState("1");
  const [tradeDate, setTradeDate] = useState(today);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setError("");
    const parsedLots = parseInt(lots, 10);
    if (!query.trim()) {
      setError(t("portfolio.tradeSymbolRequired"));
      return;
    }
    if (!Number.isFinite(parsedLots) || parsedLots <= 0) {
      setError(t("portfolio.tradeLotsRequired"));
      return;
    }
    if (side === "buy") {
      const cost = parseFloat(costPrice);
      if (!Number.isFinite(cost) || cost <= 0) {
        setError(t("portfolio.invalidCost"));
        return;
      }
      if (!tradeDate) {
        setError(t("portfolio.tradeDateRequired"));
        return;
      }
    }

    setSubmitting(true);
    try {
      const tx = await buildPayload(side, query, costPrice, lots, tradeDate);
      const sellError = validateSellQuantities([tx], holdings, t);
      if (sellError) {
        setError(sellError);
        return;
      }
      await api.applyHoldingTransactions({ transactions: [tx] });
      await onApplied();
      onCancel();
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <li className="lists-holding-inline-trade">
      <div className="lists-inline-trade-form">
        <label className="lists-inline-field">
          <span>{t("portfolio.tradeSide")}</span>
          <select
            value={side}
            onChange={(e) => setSide(e.target.value as "buy" | "sell")}
          >
            <option value="buy">{t("portfolio.tradeSideBuy")}</option>
            <option value="sell">{t("portfolio.tradeSideSell")}</option>
          </select>
        </label>
        <label className="lists-inline-field lists-inline-field-wide">
          <span>{t("portfolio.tradeSymbol")}</span>
          <input
            placeholder={t("portfolio.symbolPh")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        {side === "buy" && (
          <>
            <label className="lists-inline-field">
              <span>{t("portfolio.tradeDate")}</span>
              <input
                type="date"
                required
                max={today}
                value={tradeDate}
                onChange={(e) => setTradeDate(e.target.value)}
              />
            </label>
            <label className="lists-inline-field">
              <span>{t("portfolio.tradeCost")}</span>
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="0.00"
                value={costPrice}
                onChange={(e) => setCostPrice(e.target.value)}
              />
            </label>
          </>
        )}
        <label className="lists-inline-field">
          <span>{t("portfolio.tradeLots")}</span>
          <input
            type="number"
            min="1"
            step="1"
            value={lots}
            onChange={(e) => setLots(e.target.value)}
          />
        </label>
        <div className="lists-inline-trade-actions">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onCancel}
            disabled={submitting}
          >
            {t("settings.cancel")}
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => void submit()}
            disabled={submitting}
          >
            {submitting
              ? t("portfolio.tradeSubmitting")
              : t("portfolio.tradeSubmit")}
          </button>
        </div>
      </div>
      {error && <p className="error lists-inline-trade-error">{error}</p>}
    </li>
  );
}
