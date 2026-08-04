import { useEffect, useMemo, useState } from "react";
import {
  api,
  type IndexIntraday,
  type MarketOverview,
  type NewsItem,
  type SectorBoard,
} from "./api";
import { IndexSparkCard } from "./IndexSparkCard";
import { signedClass } from "./holdingDisplay";
import { useI18n } from "./i18n";
import { localizeIndexName } from "./indexLabels";
import { SectorStripCards, type SectorStripItem } from "./SectorStripCards";
import { FactorScreenerSection } from "./PortfolioEventsScreener";
import { localizeSentiment } from "./uiLabels";
import { SentimentGauge } from "./SentimentGauge";
import { loadModeSettings } from "./modeSettings";

interface MarketPanelProps {
  overview: MarketOverview | null;
  overviewLoading: boolean;
  onRefreshOverview: () => void;
  news: NewsItem[];
  newsLoading: boolean;
  onLoadNews: () => void;
  onIndexClick: (name: string) => void;
  onSectorClick: (sectorName: string) => void;
  onAskCopilot?: (query: string) => void;
}

export function MarketPanel({
  overview,
  overviewLoading,
  onRefreshOverview,
  news,
  newsLoading,
  onLoadNews,
  onIndexClick,
  onSectorClick,
  onAskCopilot,
}: MarketPanelProps) {
  const { t, locale } = useI18n();
  const [sectors, setSectors] = useState<SectorBoard[]>([]);
  const [sectorsLoading, setSectorsLoading] = useState(true);
  const [intraday, setIntraday] = useState<Record<string, IndexIntraday>>({});

  useEffect(() => {
    setSectorsLoading(true);
    api
      .sectorBoardsAll()
      .then((resp) => setSectors(resp.boards ?? []))
      .catch(() => setSectors([]))
      .finally(() => setSectorsLoading(false));
  }, []);

  const indexSymbols = useMemo(
    () =>
      (overview?.indices ?? [])
        .map((idx) => idx.symbol)
        .filter((sym): sym is string => Boolean(sym && /^\d{6}$/.test(sym))),
    [overview?.indices],
  );

  useEffect(() => {
    if (indexSymbols.length === 0) return;
    let cancelled = false;
    api
      .indexIntraday(indexSymbols)
      .then((rows) => {
        if (cancelled) return;
        const map: Record<string, IndexIntraday> = {};
        rows.forEach((row) => {
          map[row.symbol] = row;
        });
        setIntraday(map);
      })
      .catch(() => {
        if (!cancelled) setIntraday({});
      });
    return () => {
      cancelled = true;
    };
  }, [indexSymbols.join(",")]);

  const marketNews = useMemo(
    () =>
      news.filter((item) => item.category === "market" || item.category === "sector").slice(0, 16),
    [news],
  );

  const sectorCards: SectorStripItem[] = useMemo(
    () =>
      [...sectors]
        .sort((a, b) => a.change_pct - b.change_pct)
        .map((board) => ({
          id: board.code,
          label: board.name,
          value: board.change_pct,
          meta: board.leader_name || undefined,
          onClick: () => onSectorClick(board.name),
        })),
    [sectors, onSectorClick],
  );

  return (
    <div className="panel market-panel">
      <div className="panel-actions-row">
        <button className="btn btn-primary" onClick={onRefreshOverview} disabled={overviewLoading}>
          {overviewLoading ? t("market.loading") : t("market.refresh")}
        </button>
        <button className="btn btn-ghost" onClick={onLoadNews} disabled={newsLoading}>
          {newsLoading ? t("news.loading") : t("market.refreshNews")}
        </button>
      </div>

      <section className="market-section">
        <h3 className="market-section-title">{t("market.indicesTitle")}</h3>
        {overviewLoading && !overview ? (
          <p className="muted">{t("market.loading")}</p>
        ) : (
          <>
            <div className="index-spark-grid">
              {(overview?.indices ?? []).map((idx) => {
                const label = localizeIndexName(idx.symbol, idx.name, t);
                const sym = idx.symbol ?? "";
                return (
                  <IndexSparkCard
                    key={sym || idx.name}
                    name={label}
                    symbol={sym}
                    price={idx.price}
                    changePct={idx.change_pct}
                    intraday={sym ? intraday[sym] : null}
                    onClick={() => onIndexClick(label)}
                  />
                );
              })}
            </div>
          </>
        )}
        {overview && (overview.advancers != null || overview.decliners != null) && (
          <div className="market-breadth">
            <span className="muted">{t("market.breadth")}</span>
            <div className="market-breadth-bar" aria-hidden="true">
              <span
                className="market-breadth-up"
                style={{
                  flex: overview.advancers ?? 0,
                }}
              />
              <span
                className="market-breadth-down"
                style={{
                  flex: overview.decliners ?? 0,
                }}
              />
            </div>
            <span className="mono muted">
              {t("ticker.breadth", {
                up: overview.advancers ?? "—",
                down: overview.decliners ?? "—",
              })}
            </span>
          </div>
        )}
        {overview?.northbound_net_yi != null && (
          <p className="muted market-northbound">
            {t("ticker.northbound", {
              v: overview.northbound_net_yi.toFixed(1),
            })}
          </p>
        )}
      </section>

      <section className="market-section">
        <h3 className="market-section-title">{t("sentiment.marketTitle")}</h3>
        <SentimentGauge variant="market" pollingEnabled={loadModeSettings().uiPollingEnabled} />
      </section>

      <section className="market-section">
        <h3 className="market-section-title">{t("market.sectorsTitle")}</h3>
        {sectorsLoading ? (
          <p className="muted">{t("sectors.loading")}</p>
        ) : sectorCards.length === 0 ? (
          <p className="muted">{t("sectors.empty")}</p>
        ) : (
          <SectorStripCards items={sectorCards} ariaLabel={t("market.sectorsTitle")} />
        )}
      </section>

      <section className="market-section market-section-screener">
        <FactorScreenerSection />
      </section>

      <section className="market-section">
        <h3 className="market-section-title">{t("market.newsTitle")}</h3>
        {newsLoading && marketNews.length === 0 ? (
          <p className="muted">{t("news.loading")}</p>
        ) : marketNews.length === 0 ? (
          <p className="muted">{t("market.newsEmpty")}</p>
        ) : (
          <ul className="market-news-list">
            {marketNews.map((item) => (
              <li key={item.id} className="market-news-item">
                <div className="market-news-head">
                  <span
                    className={`market-news-sentiment ${signedClass(item.sentiment === "bullish" ? 1 : item.sentiment === "bearish" ? -1 : 0)}`}
                  >
                    {localizeSentiment(item.sentiment, t)}
                  </span>
                  <time className="muted market-news-time">
                    {new Date(item.published_at).toLocaleString(
                      locale === "zh" ? "zh-CN" : "en-US",
                      {
                        hour: "2-digit",
                        minute: "2-digit",
                        month: "numeric",
                        day: "numeric",
                      },
                    )}
                  </time>
                </div>
                <button
                  type="button"
                  className="market-news-title"
                  onClick={() =>
                    onAskCopilot?.(
                      locale === "zh"
                        ? `解读这条市场新闻：${item.title}`
                        : `Explain this market headline: ${item.title}`,
                    )
                  }
                >
                  {item.title}
                </button>
                {item.summary ? <p className="muted market-news-summary">{item.summary}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
