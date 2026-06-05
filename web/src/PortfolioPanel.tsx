import { useState } from "react";
import type { HoldingEnriched, StockLookupOut } from "./api";
import { formatPrice, formatSignedMoney, formatSignedPct, signedClass } from "./holdingDisplay";
import { useI18n } from "./i18n";
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
}: PortfolioPanelProps) {
  const { t } = useI18n();
  const [chartSymbol, setChartSymbol] = useState<string | null>(null);

  return (
    <div className="panel portfolio-panel">
      {holdings.length > 0 && (
        <div className="portfolio-summary">
          <div className="portfolio-summary-item">
            <span className="portfolio-summary-label">
              {t("portfolio.summaryCount").replace("{n}", String(portfolioSummary.count))}
            </span>
            <span className="portfolio-summary-value">{portfolioSummary.count}</span>
          </div>
          <div className="portfolio-summary-item">
            <span className="portfolio-summary-label">{t("portfolio.summaryValue")}</span>
            <span className="portfolio-summary-value mono">
              {portfolioSummary.hasQuotes
                ? `¥${portfolioSummary.totalValue.toLocaleString(numLocale, { maximumFractionDigits: 0 })}`
                : "—"}
            </span>
          </div>
          <div className="portfolio-summary-item">
            <span className="portfolio-summary-label">{t("portfolio.summaryToday")}</span>
            <span className={`portfolio-summary-value mono ${signedClass(portfolioSummary.todayPnl)}`}>
              {portfolioSummary.hasQuotes ? formatSignedMoney(portfolioSummary.todayPnl) : "—"}
            </span>
          </div>
        </div>
      )}
      {sectorMix.length > 0 && (
        <div className="sector-concentration">
          <span className="field-label">{t("portfolio.sectorMix")}</span>
          {sectorMix.slice(0, 4).map((s) => (
            <div className="sector-concentration-row" key={s.sector}>
              <span>{s.sector}</span>
              <div className="sector-concentration-bar">
                <div style={{ width: `${Math.min(s.pct, 100)}%` }} />
              </div>
              <span className="mono">{s.pct.toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}
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
      {holdings.length === 0 ? (
        <p className="muted holdings-empty">{t("portfolio.empty")}</p>
      ) : (
        <div className="holdings-table-wrap">
          <table className="holdings-table">
            <thead>
              <tr>
                <th>{t("portfolio.stock")}</th>
                <th>{t("portfolio.price")}</th>
                <th>{t("portfolio.change")}</th>
                <th>{t("portfolio.costCol")}</th>
                <th>{t("portfolio.qty")}</th>
                <th>{t("portfolio.pnl")}</th>
                <th>{t("portfolio.annualized")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {holdings.map((h) => (
                <tr key={h.id}>
                  <td>
                    <div className="holding-name">{h.name}</div>
                    <div className="holding-meta muted">
                      {h.symbol} · {h.sector}
                      {h.buy_date ? ` · ${h.buy_date}` : ""}
                    </div>
                  </td>
                  <td className="mono">
                    {h.quote_available ? (
                      <>
                        <span className="holding-price-label muted">{h.price_label}</span> {formatPrice(h.price ?? null)}
                      </>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td className={`mono ${signedClass(h.change_pct)}`}>
                    {h.quote_available ? formatSignedPct(h.change_pct ?? null) : "—"}
                  </td>
                  <td className="mono">{h.cost_price.toFixed(2)}</td>
                  <td className="mono">{h.quantity}</td>
                  <td className={signedClass(h.profit_pct)}>
                    {h.quote_available ? (
                      <>
                        <div className="mono">{formatSignedMoney(h.profit_amount ?? null)}</div>
                        <div className="mono holdings-sub">{formatSignedPct(h.profit_pct ?? null)}</div>
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className={`mono ${signedClass(h.annualized_pct)}`}>
                    {h.annualized_pct != null ? formatSignedPct(h.annualized_pct) : "—"}
                  </td>
                          <td>
                            <button type="button" className="btn btn-ghost btn-sm" onClick={() => onAnalyzeHolding(h)}>
                              {t("portfolio.analyze")}
                            </button>{" "}
                            <button
                              type="button"
                              className={`btn btn-ghost btn-sm${chartSymbol === h.symbol ? " active" : ""}`}
                              onClick={() => setChartSymbol(chartSymbol === h.symbol ? null : h.symbol)}
                            >
                              {t("portfolio.chart")}
                            </button>{" "}
                            <button type="button" className="delete-btn" onClick={() => h.id && onDeleteHolding(h.id)}>
                              DEL
                            </button>
                          </td>
                </tr>
              ))}
            </tbody>
          </table>
              </div>
              )}
              {chartSymbol && (
                <div className="portfolio-chart-panel">
                  <StockChart symbol={chartSymbol} />
                </div>
              )}
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
    </div>
  );
}
