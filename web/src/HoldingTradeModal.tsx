import { useEffect, useState } from "react";
import { api, type HoldingEnriched, type HoldingTransactionItem } from "./api";
import { useI18n } from "./i18n";

const LOTS_SIZE = 100;

export interface TradeDraft {
  key: string;
  side: "buy" | "sell";
  query: string;
  symbol: string;
  name: string;
  costPrice: string;
  lots: string;
  tradeDate: string;
}

interface HoldingTradeModalProps {
  open: boolean;
  holdings: HoldingEnriched[];
  onClose: () => void;
  onApplied: () => void | Promise<void>;
  initialRow?: Partial<TradeDraft> | null;
}

function emptyRow(): TradeDraft {
  const today = new Date().toISOString().slice(0, 10);
  return {
    key: crypto.randomUUID(),
    side: "buy",
    query: "",
    symbol: "",
    name: "",
    costPrice: "",
    lots: "1",
    tradeDate: today,
  };
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

function validateDraftRows(
  rows: TradeDraft[],
  t: (key: string) => string,
): string | null {
  if (rows.length === 0) return t("portfolio.tradeEmpty");
  for (const row of rows) {
    const lots = parseInt(row.lots, 10);
    if (!row.query.trim()) return t("portfolio.tradeSymbolRequired");
    if (!Number.isFinite(lots) || lots <= 0)
      return t("portfolio.tradeLotsRequired");
    if (row.side === "buy") {
      const cost = parseFloat(row.costPrice);
      if (!Number.isFinite(cost) || cost <= 0)
        return t("portfolio.invalidCost");
      if (!row.tradeDate) return t("portfolio.tradeDateRequired");
    }
  }
  return null;
}

async function buildPayload(
  rows: TradeDraft[],
): Promise<HoldingTransactionItem[]> {
  const payload: HoldingTransactionItem[] = [];
  for (const row of rows) {
    const lots = parseInt(row.lots, 10);
    let symbol = row.symbol || undefined;
    let name = row.name || undefined;
    let query = row.query.trim() || undefined;

    if (!symbol && query) {
      const lookup = await api.lookupStock(query);
      if (lookup.status === "ambiguous") {
        throw new Error(lookup.message || query);
      }
      if (lookup.status !== "confirmed" || !lookup.symbol || !lookup.name) {
        throw new Error(lookup.message || query);
      }
      symbol = lookup.symbol;
      name = lookup.name;
      query = undefined;
    }

    payload.push({
      side: row.side,
      symbol,
      name,
      query,
      lots,
      cost_price: row.side === "buy" ? parseFloat(row.costPrice) : undefined,
      trade_date: row.side === "buy" ? row.tradeDate : undefined,
    });
  }
  return payload;
}

export function HoldingTradeModal({
  open,
  holdings,
  onClose,
  onApplied,
  initialRow = null,
}: HoldingTradeModalProps) {
  const { t } = useI18n();
  const [rows, setRows] = useState<TradeDraft[]>(() => [emptyRow()]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      const base = emptyRow();
      const seed = initialRow
        ? {
            ...base,
            ...initialRow,
            query:
              initialRow.query ?? initialRow.name ?? initialRow.symbol ?? "",
          }
        : base;
      setRows([seed]);
      setError("");
    }
  }, [open, initialRow]);

  if (!open) return null;

  function updateRow(key: string, patch: Partial<TradeDraft>) {
    setRows((prev) =>
      prev.map((r) => (r.key === key ? { ...r, ...patch } : r)),
    );
  }

  function addRow() {
    setRows((prev) => [...prev, emptyRow()]);
  }

  function removeRow(key: string) {
    setRows((prev) =>
      prev.length <= 1 ? prev : prev.filter((r) => r.key !== key),
    );
  }

  async function submit() {
    setError("");
    const draftError = validateDraftRows(rows, t);
    if (draftError) {
      setError(draftError);
      return;
    }

    setSubmitting(true);
    try {
      const transactions = await buildPayload(rows);
      const sellError = validateSellQuantities(transactions, holdings, t);
      if (sellError) {
        setError(sellError);
        return;
      }
      await api.applyHoldingTransactions({ transactions });
      await onApplied();
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" role="presentation" onMouseDown={onClose}>
      <div
        className="modal holding-trade-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="holding-trade-title"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="modal-header">
          <h3 id="holding-trade-title">{t("portfolio.tradeModalTitle")}</h3>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label={t("settings.close")}
          >
            ×
          </button>
        </header>
        <div className="modal-body">
          <p className="muted holding-trade-hint">
            {t("portfolio.tradeModalHint")}
          </p>
          <div className="holding-trade-rows">
            {rows.map((row, index) => (
              <div key={row.key} className="holding-trade-row">
                <div className="holding-trade-row-head">
                  <span className="field-label">
                    {t("portfolio.tradeRow", { n: String(index + 1) })}
                  </span>
                  {rows.length > 1 && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => removeRow(row.key)}
                    >
                      {t("portfolio.tradeRemoveRow")}
                    </button>
                  )}
                </div>
                <div className="holding-trade-fields">
                  <label className="field">
                    <span className="field-label">
                      {t("portfolio.tradeSide")}
                    </span>
                    <select
                      value={row.side}
                      onChange={(e) =>
                        updateRow(row.key, {
                          side: e.target.value as "buy" | "sell",
                        })
                      }
                    >
                      <option value="buy">{t("portfolio.tradeSideBuy")}</option>
                      <option value="sell">
                        {t("portfolio.tradeSideSell")}
                      </option>
                    </select>
                  </label>
                  <label className="field field-wide">
                    <span className="field-label">
                      {t("portfolio.tradeSymbol")}
                    </span>
                    <input
                      placeholder={t("portfolio.symbolPh")}
                      value={row.query}
                      onChange={(e) =>
                        updateRow(row.key, {
                          query: e.target.value,
                          symbol: "",
                          name: "",
                        })
                      }
                    />
                  </label>
                  {row.side === "buy" && (
                    <>
                      <label className="field">
                        <span className="field-label">
                          {t("portfolio.tradeDate")}
                        </span>
                        <input
                          type="date"
                          required
                          max={new Date().toISOString().slice(0, 10)}
                          value={row.tradeDate}
                          onChange={(e) =>
                            updateRow(row.key, { tradeDate: e.target.value })
                          }
                        />
                      </label>
                      <label className="field">
                        <span className="field-label">
                          {t("portfolio.tradeCost")}
                        </span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          placeholder="0.00"
                          value={row.costPrice}
                          onChange={(e) =>
                            updateRow(row.key, { costPrice: e.target.value })
                          }
                        />
                      </label>
                    </>
                  )}
                  <label className="field">
                    <span className="field-label">
                      {t("portfolio.tradeLots")}
                    </span>
                    <input
                      type="number"
                      min="1"
                      step="1"
                      value={row.lots}
                      onChange={(e) =>
                        updateRow(row.key, { lots: e.target.value })
                      }
                    />
                  </label>
                </div>
              </div>
            ))}
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={addRow}
          >
            {t("portfolio.tradeAddRow")}
          </button>
          {error && <p className="error holding-trade-error">{error}</p>}
        </div>
        <footer className="modal-footer">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={onClose}
            disabled={submitting}
          >
            {t("settings.cancel")}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void submit()}
            disabled={submitting}
          >
            {submitting
              ? t("portfolio.tradeSubmitting")
              : t("portfolio.tradeSubmit")}
          </button>
        </footer>
      </div>
    </div>
  );
}
