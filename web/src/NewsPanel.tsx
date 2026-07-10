import { useMemo, useState } from "react";
import { api, type Briefing, type NewsItem, type SectorPreferences } from "./api";
import { getBriefingKind } from "./briefingKind";
import { useI18n } from "./i18n";
import { NewsAnalysisModal } from "./NewsAnalysisModal";
import { localizeBriefing, localizeImpactLevel, localizeSentiment } from "./uiLabels";

interface NewsPanelProps {
  news: NewsItem[];
  newsLoading: boolean;
  newsSectors: SectorPreferences | null;
  sectorSaving: boolean;
  onLoadNews: () => void;
  onToggleSector: (sector: string) => void;
  onAskCopilot?: (query: string) => void;
}

export function NewsPanel({
  news,
  newsLoading,
  newsSectors,
  sectorSaving,
  onLoadNews,
  onToggleSector,
  onAskCopilot,
}: NewsPanelProps) {
  const { t } = useI18n();
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [analyzingNews, setAnalyzingNews] = useState<NewsItem | null>(null);
  const briefingKind = useMemo(() => getBriefingKind(), []);
  const briefingLabel =
    briefingKind === "premarket"
      ? t("news.briefingPremarket")
      : briefingKind === "intraday"
        ? t("news.briefingIntraday")
        : t("news.briefingPostMarket");

  async function loadBriefing() {
    setBriefingLoading(true);
    try {
      setBriefing(await api.generateBriefing(briefingKind));
    } finally {
      setBriefingLoading(false);
    }
  }

  return (
    <div className="panel">
      <div className="panel-actions-row">
        <button className="btn btn-primary" onClick={onLoadNews} disabled={newsLoading}>
          {newsLoading ? t("news.loading") : t("news.refresh")}
        </button>
        <button
          className="btn btn-ghost"
          disabled={briefingLoading}
          onClick={() => void loadBriefing()}
        >
          {briefingLoading ? t("news.briefingLoading") : briefingLabel}
        </button>
      </div>
      {briefing && (() => {
        const b = localizeBriefing(briefing, t);
        return (
        <div className="briefing-card">
          <h4>{b.title}</h4>
          <p>{b.summary}</p>
          <div className="briefing-vertical-list">
            {b.sections.map((s) => (
              <div key={s.title} className="briefing-point">
                <strong>{s.title}</strong>
                <pre className="briefing-section">{s.content}</pre>
              </div>
            ))}
          </div>
        </div>
        );
      })()}
      {newsSectors && newsSectors.available.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <span className="field-label">{t("news.sectors")}</span>
          <div className="sector-grid">
            {newsSectors.available.map((sector) => (
              <button
                key={sector}
                type="button"
                className={`sector-chip${newsSectors.selected.includes(sector) ? " active" : ""}`}
                disabled={sectorSaving}
                onClick={() => onToggleSector(sector)}
              >
                {sector}
              </button>
            ))}
          </div>
        </div>
      )}
      {(["holding", "sector", "market"] as const).map((group) => {
        const items = news.filter((n) => {
          if (group === "holding") return n.category === "holding" || n.related_to_user;
          if (group === "sector") return n.category === "sector" && !n.related_to_user;
          return n.category === "market" && !n.related_to_user;
        });
        if (items.length === 0) return null;
        const title =
          group === "market" ? t("news.groupMarket") : group === "sector" ? t("news.groupSector") : t("news.groupHolding");
        return (
          <div key={group}>
            <p className="news-group-title">{title}</p>
            {items.map((n) => (
              <div
                className={`card${n.related_to_user || n.category === "holding" ? " news-card-related" : ""}`}
                key={n.id}
                onClick={() => setAnalyzingNews(n)}
                title={t("news.clickToAnalyze")}
                style={{ cursor: "pointer" }}
              >
                <h4>{n.title}</h4>
                <p>{n.summary}</p>
                <span
                  className={`stat-pill ${n.sentiment === "bullish" ? "up" : n.sentiment === "bearish" ? "down" : ""}`}
                >
                  {localizeSentiment(n.sentiment, t)} · {localizeImpactLevel(n.impact_level, t)}
                  {n.related_to_user ? ` · ${t("news.related")}` : ""}
                </span>
                {onAskCopilot && (
                  <div
                    className="ai-action-row news-action-row"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => onAskCopilot(`${t("news.askExplain")}：${n.title}`)}
                    >
                      {t("news.askExplain")}
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => onAskCopilot(`${t("news.askImpact")}：${n.title}`)}
                    >
                      {t("news.askImpact")}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        );
      })}
      {news.length === 0 && !newsLoading && <p className="muted">{t("news.empty")}</p>}
      {analyzingNews && (
        <NewsAnalysisModal
          newsId={analyzingNews.id}
          title={analyzingNews.title}
          summary={analyzingNews.summary}
          source={analyzingNews.source}
          sentiment={analyzingNews.sentiment}
          impactLevel={analyzingNews.impact_level}
          entities={analyzingNews.entities}
          onClose={() => setAnalyzingNews(null)}
        />
      )}
    </div>
  );
}
