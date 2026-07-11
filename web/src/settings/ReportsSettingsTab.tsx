import { api, type MemorySearchResult, type ResearchReportListItem, type SignalBacktest } from "../api";
import { useI18n } from "../i18n";

interface ReportsSettingsTabProps {
  reports: ResearchReportListItem[];
  backtest: SignalBacktest | null;
  memoryQuery: string;
  memoryHits: MemorySearchResult | null;
  onMemoryQueryChange: (value: string) => void;
  onMemorySearch: (query: string) => void;
}

export function ReportsSettingsTab({
  reports,
  backtest,
  memoryQuery,
  memoryHits,
  onMemoryQueryChange,
  onMemorySearch,
}: ReportsSettingsTabProps) {
  const { t, locale } = useI18n();

  return (
    <>
      <h4 className="settings-section-title">{t("settings.reportHistory")}</h4>
      <p className="settings-hint">{t("settings.reportHistoryHint")}</p>
      {reports.length === 0 ? (
        <p className="settings-muted">{t("settings.reportEmpty")}</p>
      ) : (
        <ul className="report-history-list">
          {reports.map((r) => (
            <li key={r.id} className="report-history-item">
              <div className="report-history-main">
                <strong>
                  {r.name} ({r.symbol})
                </strong>
                <span className="settings-muted">
                  {r.composite_score}/10 ·{" "}
                  {r.has_debate ? t("settings.reportDebate") : t("settings.reportResearchOnly")}
                </span>
                <span className="settings-muted report-history-time">
                  {new Date(r.created_at).toLocaleString(locale === "zh" ? "zh-CN" : "en-US")}
                </span>
              </div>
              <div className="report-history-actions">
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => api.downloadReportMarkdown(r.id)}
                >
                  {t("settings.reportExport")}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => api.downloadReportPdf(r.id)}
                >
                  {t("settings.reportExportPdf")}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <h4 className="settings-section-title">{t("settings.signalBacktest")}</h4>
      <p className="settings-hint">{t("settings.signalBacktestHint")}</p>
      {backtest?.sample_bias_note ? (
        <p className="settings-muted">{backtest.sample_bias_note}</p>
      ) : null}
      {backtest?.notes?.map((note) => (
        <p className="settings-muted" key={note}>
          {note}
        </p>
      ))}
      {backtest && backtest.horizons.some((h) => h.sample_count > 0) ? (
        <ul className="report-history-list">
          {backtest.horizons.map((h) => (
            <li key={h.days} className="settings-muted">
              {t("settings.signalBacktestRow", {
                days: String(h.days),
                n: String(h.sample_count),
                bull: h.bullish_avg_return_pct != null ? String(h.bullish_avg_return_pct) : "—",
                bear: h.bearish_avg_return_pct != null ? String(h.bearish_avg_return_pct) : "—",
              })}
            </li>
          ))}
        </ul>
      ) : (
        <p className="settings-muted">{t("settings.signalBacktestEmpty")}</p>
      )}

      <h4 className="settings-section-title">{t("settings.memorySearch")}</h4>
      <p className="settings-hint">{t("settings.memorySearchHint")}</p>
      <div className="settings-memory-row">
        <input
          type="search"
          value={memoryQuery}
          placeholder={t("settings.memorySearchPh")}
          onChange={(e) => onMemoryQueryChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && memoryQuery.trim()) {
              onMemorySearch(memoryQuery.trim());
            }
          }}
        />
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          disabled={!memoryQuery.trim()}
          onClick={() => onMemorySearch(memoryQuery.trim())}
        >
          {t("settings.memorySearchBtn")}
        </button>
      </div>
      {memoryHits && (
        <ul className="report-history-list">
          {memoryHits.hits.length === 0 ? (
            <li className="settings-muted">{t("settings.memoryEmpty")}</li>
          ) : (
            memoryHits.hits.map((hit) => (
              <li key={hit.report_id} className="report-history-item">
                <strong>
                  {hit.name} ({hit.symbol})
                </strong>
                <span className="settings-muted">
                  {hit.composite_score}/10 · {hit.bias}
                </span>
                <p className="settings-muted">{hit.summary}</p>
              </li>
            ))
          )}
        </ul>
      )}
    </>
  );
}
