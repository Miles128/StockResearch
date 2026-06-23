import type { MarketOverview } from "./api";
import { useI18n } from "./i18n";

interface MarketPanelProps {
  overview: MarketOverview | null;
  loading: boolean;
  onRefresh: () => void;
  onAskCopilot: (query: string) => void;
}

export function MarketPanel({
  overview,
  loading,
  onRefresh,
  onAskCopilot,
}: MarketPanelProps) {
  const { t, locale } = useI18n();
  const breadth =
    overview?.advancers != null && overview.decliners != null
      ? `${overview.advancers} / ${overview.decliners}`
      : "—";

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
        <div className="market-state-card">
          <span>{locale === "zh" ? "涨 / 跌家数" : "Advancers / Decliners"}</span>
          <strong>{breadth}</strong>
        </div>
        <div className="market-state-card">
          <span>{locale === "zh" ? "北向资金" : "Northbound"}</span>
          <strong>
            {overview?.northbound_net_yi == null
              ? "—"
              : `${overview.northbound_net_yi > 0 ? "+" : ""}${overview.northbound_net_yi.toFixed(1)} 亿`}
          </strong>
        </div>
        <div className="market-state-card">
          <span>{locale === "zh" ? "数据来源" : "Source"}</span>
          <strong>{overview?.source || "—"}</strong>
        </div>
      </div>

      <div className="market-index-grid">
        {overview?.indices.map((index) => (
          <button
            type="button"
            className="market-index-card"
            key={index.symbol || index.name}
            onClick={() =>
              onAskCopilot(
                locale === "zh"
                  ? `分析${index.name}今天的走势和主要驱动`
                  : `Analyze today's move and drivers for ${index.name}`,
              )
            }
          >
            <span>{index.name}</span>
            <strong>{index.price.toFixed(2)}</strong>
            <em className={index.change_pct >= 0 ? "up" : "down"}>
              {index.change_pct >= 0 ? "+" : ""}
              {index.change_pct.toFixed(2)}%
            </em>
          </button>
        ))}
      </div>
      {!overview && !loading && <p className="muted">{t("header.dataUnknown")}</p>}
    </div>
  );
}
