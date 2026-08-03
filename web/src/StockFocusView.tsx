import { useMemo } from "react";
import type { NewsItem } from "./api";
import { formatPrice, formatSignedPct, signedClass } from "./holdingDisplay";
import { useI18n } from "./i18n";
import { indexSearchTerms } from "./indexLabels";
import type { FocusContext } from "./layoutTypes";
import { CollapsibleSection } from "./CollapsibleSection";
import { MarketChart } from "./StockChart";
import { localizeImpactLevel, localizeSentiment } from "./uiLabels";
import { IconExternalLink, IconRefresh } from "./ui/Icons";
import { SentimentGauge } from "./SentimentGauge";
import { loadModeSettings } from "./modeSettings";

interface StockFocusViewProps {
  focus: FocusContext;
  news: NewsItem[];
  newsLoading: boolean;
  onAnalyze: () => void;
  onLoadNews: () => void;
}

function filterNews(focus: FocusContext, news: NewsItem[]): NewsItem[] {
  if (focus.kind === "stock") {
    return news.filter(
      (n) =>
        n.entities.some(
          (e) => e.includes(focus.symbol) || e.includes(focus.name),
        ) ||
        n.title.includes(focus.name) ||
        n.title.includes(focus.symbol) ||
        n.summary.includes(focus.name) ||
        n.summary.includes(focus.symbol),
    );
  }
  if (focus.kind === "index") {
    const needles = indexSearchTerms(focus.symbol, focus.name);
    const market = news.filter((n) => n.category === "market");
    const matched = news.filter((n) =>
      needles.some(
        (needle) =>
          n.title.includes(needle) ||
          n.summary.includes(needle) ||
          n.entities.some((e) => e.includes(needle)),
      ),
    );
    const merged = [...matched];
    for (const item of market) {
      if (!merged.some((row) => row.id === item.id)) merged.push(item);
    }
    return merged;
  }
  const needle = focus.name;
  return news.filter(
    (n) =>
      n.category === "sector" ||
      n.title.includes(needle) ||
      n.summary.includes(needle) ||
      n.entities.some((e) => e.includes(needle)),
  );
}

export function StockFocusView({
  focus,
  news,
  newsLoading,
  onAnalyze,
  onLoadNews,
}: StockFocusViewProps) {
  const { t } = useI18n();
  const filteredNews = useMemo(() => filterNews(focus, news), [focus, news]);
  const changeClass = signedClass(
    focus.kind === "stock" ? (focus.change_pct ?? 0) : 0,
  );

  return (
    <div className="stock-focus-view">
      {focus.kind === "stock" && (
        <>
          <CollapsibleSection
            title={t("stockFocus.quote")}
            summary={focus.symbol}
          >
            <div className="stock-focus-metrics">
              <span className={`mono stock-focus-price ${changeClass}`}>
                {focus.price != null ? formatPrice(focus.price) : "—"}
              </span>
              <span className={`mono ${changeClass}`}>
                {focus.change_pct != null
                  ? formatSignedPct(focus.change_pct)
                  : ""}
              </span>
              <button
                type="button"
                className="icon-btn"
                onClick={onAnalyze}
                title={t("portfolio.analyze")}
                aria-label={t("portfolio.analyze")}
              >
                <IconExternalLink />
              </button>
            </div>
            <p className="muted stock-focus-financial-hint">
              {t("stockFocus.financialHint")}
            </p>
          </CollapsibleSection>

          <CollapsibleSection title={t("chart.price")}>
            <MarketChart key={focus.symbol} symbol={focus.symbol} />
          </CollapsibleSection>
        </>
      )}

      {focus.kind === "index" && (
        <CollapsibleSection title={t("chart.price")} summary={focus.name}>
          <MarketChart
            key={focus.symbol}
            symbol={focus.symbol}
            variant="index"
          />
        </CollapsibleSection>
      )}

      {focus.kind === "sector" && (
        <CollapsibleSection title={t("stockFocus.sector")} summary={focus.name}>
          <p className="muted">{t("stockFocus.sectorHint")}</p>
        </CollapsibleSection>
      )}

      {focus.kind === "stock" && (
        <CollapsibleSection title={t("sentiment.stockTitle")}>
          <SentimentGauge
            variant="stock"
            symbol={focus.symbol}
            name={focus.name}
            pollingEnabled={loadModeSettings().uiPollingEnabled}
          />
        </CollapsibleSection>
      )}

      <CollapsibleSection
        title={t("stockFocus.relatedNews")}
        summary={filteredNews.length ? String(filteredNews.length) : undefined}
      >
        <div className="stock-focus-news-actions">
          <button
            type="button"
            className="icon-btn"
            onClick={onLoadNews}
            disabled={newsLoading}
            title={t("news.refresh")}
            aria-label={t("news.refresh")}
          >
            <IconRefresh />
          </button>
        </div>
        {filteredNews.length === 0 && !newsLoading && (
          <p className="muted flat-empty">{t("stockFocus.noNews")}</p>
        )}
        <ul className="stock-focus-news-list">
          {filteredNews.map((n) => (
            <li key={n.id} className="stock-focus-news-item">
              <div className="stock-focus-news-title">{n.title}</div>
              <p className="muted">{n.summary}</p>
              <span
                className={`stat-pill ${n.sentiment === "bullish" ? "up" : n.sentiment === "bearish" ? "down" : ""}`}
              >
                {localizeSentiment(n.sentiment, t)} ·{" "}
                {localizeImpactLevel(n.impact_level, t)}
              </span>
            </li>
          ))}
        </ul>
      </CollapsibleSection>
    </div>
  );
}
