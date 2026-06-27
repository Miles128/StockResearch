import type { MarketOverview } from "./api";
import { QuoteValues } from "./ui/DataValue";
import { UiCard } from "./ui/UiCard";
import { indexSymbolKey, localizeIndexName } from "./indexLabels";
import { useI18n } from "./i18n";
import { MarketChart } from "./StockChart";

export interface SelectedMarketIndex {
  symbol: string;
  name: string;
}

interface MarketPanelProps {
  overview: MarketOverview | null;
  loading: boolean;
  onRefresh: () => void;
  onAskCopilot: (query: string) => void;
  selectedIndex: SelectedMarketIndex | null;
  onSelectIndex: (index: SelectedMarketIndex | null) => void;
}

export function MarketPanel({
  overview,
  loading,
  onRefresh,
  onAskCopilot,
  selectedIndex,
  onSelectIndex,
}: MarketPanelProps) {
  const { t, locale } = useI18n();
  const breadth =
    overview?.advancers != null && overview.decliners != null
      ? `${overview.advancers} / ${overview.decliners}`
      : "—";

  function resolveIndex(index: NonNullable<MarketOverview["indices"]>[number]): SelectedMarketIndex | null {
    const name = localizeIndexName(index.symbol, index.name, t);
    const symbol = indexSymbolKey(index.symbol, index.name);
    if (!symbol) return null;
    return { symbol, name };
  }

  function toggleIndex(index: NonNullable<MarketOverview["indices"]>[number]) {
    const resolved = resolveIndex(index);
    if (!resolved) return;
    if (selectedIndex?.symbol === resolved.symbol) {
      onSelectIndex(null);
      return;
    }
    onSelectIndex(resolved);
  }

  return (
    <div className="panel market-canvas">
      <div className="canvas-section-heading">
        <div>
          <span className="canvas-kicker">{locale === "zh" ? "MARKET STATE" : "MARKET STATE"}</span>
          <h2>{locale === "zh" ? "市场现在处于什么状态？" : "What state is the market in?"}</h2>
        </div>
        <div className="panel-actions-row">
          <button type="button" className="btn btn-ghost" onClick={onRefresh} disabled={loading}>
            {loading ? t("news.loading") : t("ticker.refresh")}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onAskCopilot(t("chat.exampleMarketQuery"))}
          >
            {locale === "zh" ? "问 AI 解读市场" : "Ask AI about the market"}
          </button>
        </div>
      </div>

      <div className="market-state-grid">
        <UiCard className="market-state-card" title={locale === "zh" ? "涨 / 跌家数" : "Advancers / Decliners"}>
          <strong className="ui-quote-price mono">{breadth}</strong>
        </UiCard>
        <UiCard className="market-state-card" title={locale === "zh" ? "北向资金" : "Northbound"}>
          <strong className={`mono ${overview?.northbound_net_yi != null && overview.northbound_net_yi >= 0 ? "up" : overview?.northbound_net_yi != null ? "down" : ""}`}>
            {overview?.northbound_net_yi == null
              ? "—"
              : `${overview.northbound_net_yi > 0 ? "+" : ""}${overview.northbound_net_yi.toFixed(1)} 亿`}
          </strong>
        </UiCard>
        <UiCard className="market-state-card" title={locale === "zh" ? "数据来源" : "Source"}>
          <strong className="ui-quote-price mono">{overview?.source || "—"}</strong>
        </UiCard>
      </div>

      <div className="market-index-grid">
        {overview?.indices.map((index) => {
          const label = localizeIndexName(index.symbol, index.name, t);
          const resolved = resolveIndex(index);
          const active = resolved != null && selectedIndex?.symbol === resolved.symbol;
          return (
            <UiCard
              as="button"
              key={index.symbol || index.name}
              className="market-index-card"
              active={active}
              title={label}
              onClick={() => toggleIndex(index)}
            >
              <QuoteValues price={index.price} changePct={index.change_pct} />
            </UiCard>
          );
        })}
      </div>

      {selectedIndex && (
        <div className="market-chart-panel">
          <div className="market-chart-panel-head">
            <strong>{selectedIndex.name}</strong>
            <span className="muted">{selectedIndex.symbol}</span>
          </div>
          <MarketChart symbol={selectedIndex.symbol} variant="index" />
        </div>
      )}

      {!overview && !loading && <p className="muted">{t("header.dataUnknown")}</p>}
    </div>
  );
}
