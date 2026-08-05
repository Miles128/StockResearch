import { memo } from "react";
import type { MarketOverview } from "../api";
import { HeaderSearch } from "../HeaderSearch";
import { MarketTicker } from "../MarketTicker";
import { ModeSwitcher } from "../ModeSwitcher";
import { PriceAlertBell } from "../PriceAlertBell";
import { READING_MODE_I18N_KEYS, type AppMode, type ModeSettings } from "../modeSettings";
import type { TParams } from "../i18n";
import { IconSettings } from "../ui/Icons";

interface AppHeaderProps {
  t: (key: string, params?: TParams) => string;
  locale: string;
  overview: MarketOverview | null;
  overviewLoading: boolean;
  sessionLabel: string;
  modeSettings: ModeSettings;
  onSelectStock: (symbol: string, name: string) => void;
  onAskQuery: (query: string) => void;
  onRefreshOverview: () => void;
  onIndexClick: (name: string) => void;
  onSwitchMode: (mode: AppMode) => void;
  onOpenSettings: () => void;
  onToggleLocale: () => void;
}

/** Top chrome bar; memoized so chat-streaming churn in App does not re-render it. */
export const AppHeader = memo(function AppHeader({
  t,
  locale,
  overview,
  overviewLoading,
  sessionLabel,
  modeSettings,
  onSelectStock,
  onAskQuery,
  onRefreshOverview,
  onIndexClick,
  onSwitchMode,
  onOpenSettings,
  onToggleLocale,
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
