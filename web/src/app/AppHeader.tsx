import { memo } from "react";
import type { DataSourceStatus, LlmUsage, MarketOverview } from "../api";
import { HeaderSearch } from "../HeaderSearch";
import { MarketTicker } from "../MarketTicker";
import { ModeSwitcher } from "../ModeSwitcher";
import { PriceAlertBell } from "../PriceAlertBell";
import { formatHeaderUsage, formatLlmUsage } from "../llmUsageFormat";
import { READING_MODE_I18N_KEYS, type AppMode, type ModeSettings } from "../modeSettings";
import type { TParams } from "../i18n";
import { IconSettings, IconSignal } from "../ui/Icons";

interface AppHeaderProps {
  t: (key: string, params?: TParams) => string;
  locale: string;
  overview: MarketOverview | null;
  overviewLoading: boolean;
  sessionLabel: string;
  dataStatus: DataSourceStatus | null;
  headerUsage: LlmUsage | null;
  modeSettings: ModeSettings;
  onSelectStock: (symbol: string, name: string) => void;
  onAskQuery: (query: string) => void;
  onRefreshOverview: () => void;
  onIndexClick: (name: string) => void;
  onSwitchMode: (mode: AppMode) => void;
  onOpenSettings: () => void;
  onToggleLocale: () => void;
  onOpenDataDetails: () => void;
}

function dataSourceLabel(
  t: (key: string, params?: TParams) => string,
  dataStatus: DataSourceStatus | null,
): string {
  if (!dataStatus) return t("header.dataUnknown");
  const overview = dataStatus.overview;
  const quotes = dataStatus.quotes;
  const primary = overview?.primary || quotes?.primary || "sina";
  const fallback = overview?.fallback || quotes?.fallback || "akshare";
  const degraded = Boolean(overview?.degraded || quotes?.degraded);
  if (degraded) {
    return t("header.dataDegraded").replace("{primary}", primary).replace("{fallback}", fallback);
  }
  // 默认并列展示主源 + 备源，让用户看到完整源链路
  return t("header.dataLiveMulti").replace("{primary}", primary).replace("{fallback}", fallback);
}

/** Top chrome bar; memoized so chat-streaming churn in App does not re-render it. */
export const AppHeader = memo(function AppHeader({
  t,
  locale,
  overview,
  overviewLoading,
  sessionLabel,
  dataStatus,
  headerUsage,
  modeSettings,
  onSelectStock,
  onAskQuery,
  onRefreshOverview,
  onIndexClick,
  onSwitchMode,
  onOpenSettings,
  onToggleLocale,
  onOpenDataDetails,
}: AppHeaderProps) {
  return (
    <div className="app-chrome">
      <div className="chrome-left">
        <span className="chrome-brand">StockResearch</span>
      </div>
      <HeaderSearch onSelectStock={onSelectStock} onAskQuery={onAskQuery} />
      <MarketTicker
        inline
        overview={overview}
        loading={overviewLoading}
        sessionLabel={sessionLabel}
        northboundLabel={t("ticker.northbound")}
        breadthLabel={t("ticker.breadth")}
        refreshTitle={t("ticker.refresh")}
        onRefresh={onRefreshOverview}
        onIndexClick={onIndexClick}
      />
      <div className="chrome-meta">
        <ModeSwitcher settings={modeSettings} onSwitch={onSwitchMode} />
        <PriceAlertBell
          onSelectSymbol={onSelectStock}
          pollingEnabled={modeSettings.uiPollingEnabled}
          pollingIntervalMs={modeSettings.quoteRefreshMinutes * 60_000}
        />
        {headerUsage && (
          <span className="chrome-usage" title={formatLlmUsage(headerUsage, t)}>
            {formatHeaderUsage(headerUsage, t)}
          </span>
        )}
        <button
          type="button"
          className={`icon-btn data-source-icon${dataStatus && (dataStatus.quotes?.degraded || dataStatus.overview?.degraded) ? " degraded" : ""}`}
          title={
            dataStatus?.overview?.message ||
            dataStatus?.quotes?.message ||
            dataSourceLabel(t, dataStatus)
          }
          onClick={onOpenDataDetails}
        >
          <IconSignal />
        </button>
        <button
          type="button"
          className="icon-btn"
          title={t("settings.readingModeCurrent", {
            reading: t(READING_MODE_I18N_KEYS[modeSettings.readingMode].short),
          })}
          onClick={onOpenSettings}
          aria-label={t("header.settingsTitle")}
        >
          <IconSettings />
        </button>
        <button
          type="button"
          className="locale-toggle-btn"
          onClick={onToggleLocale}
          title={locale === "zh" ? "English" : "中文"}
        >
          {locale === "zh" ? "En" : "中"}
        </button>
      </div>
    </div>
  );
});
