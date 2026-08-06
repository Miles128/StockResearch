import type { PriceAlertSettings } from "../api";
import type { AppLocale } from "../localeSettings";
import type { AppTheme } from "../themeSettings";
import type { ModeSettings, ReadingMode } from "../modeSettings";
import { useI18n } from "../i18n";
import { UsageStatsBlock } from "./UsageStatsBlock";

interface GeneralSettingsTabProps {
  modeSettings: ModeSettings;
  priceAlertSettings: PriceAlertSettings | null;
  theme: AppTheme;
  themeOptions: { id: AppTheme; label: string; hint: string }[];
  readingModeOptions: { id: ReadingMode; labelKey: string; hintKey: string }[];
  onPersistModeSettings: (next: ModeSettings) => void;
  onTogglePriceAlerts: (enabled: boolean) => void;
  onToggleUiPolling: (enabled: boolean) => void;
  onSelectTheme: (theme: AppTheme) => void;
  onSelectLocale: (locale: AppLocale) => void;
  onSelectReadingMode: (mode: ReadingMode) => void;
}

export function GeneralSettingsTab({
  modeSettings,
  priceAlertSettings,
  theme,
  themeOptions,
  readingModeOptions,
  onPersistModeSettings,
  onTogglePriceAlerts,
  onToggleUiPolling,
  onSelectTheme,
  onSelectLocale,
  onSelectReadingMode,
}: GeneralSettingsTabProps) {
  const { t, locale } = useI18n();

  return (
    <>
      <h4 className="settings-section-title">{t("settings.notificationsTitle")}</h4>
      <p className="settings-hint">{t("settings.notificationsHint")}</p>
      <label className="settings-check">
        <input
          type="checkbox"
          checked={modeSettings.briefingAutoEnabled}
          onChange={(e) =>
            onPersistModeSettings({
              ...modeSettings,
              briefingAutoEnabled: e.target.checked,
            })
          }
        />
        <span>{t("settings.briefingAuto")}</span>
      </label>
      <p className="settings-muted settings-analysis-note">{t("settings.briefingAutoNote")}</p>
      <label className="settings-check">
        <input
          type="checkbox"
          checked={priceAlertSettings?.enabled ?? true}
          onChange={(e) => void onTogglePriceAlerts(e.target.checked)}
        />
        <span>{t("settings.priceAlerts")}</span>
      </label>
      <p className="settings-muted settings-analysis-note">{t("settings.priceAlertsNote")}</p>
      <label className="settings-check">
        <input
          type="checkbox"
          checked={modeSettings.uiPollingEnabled}
          onChange={(e) => onToggleUiPolling(e.target.checked)}
        />
        <span>{t("settings.uiPolling")}</span>
      </label>
      <p className="settings-muted settings-analysis-note">{t("settings.uiPollingNote")}</p>

      <h4 className="settings-section-title">{t("settings.appearance")}</h4>
      <p className="settings-hint">{t("settings.appearanceHint")}</p>
      <div className="theme-picker">
        {themeOptions.map((opt) => (
          <button
            key={opt.id}
            type="button"
            className={`theme-option${theme === opt.id ? " active" : ""}`}
            data-theme-preview={opt.id}
            onClick={() => onSelectTheme(opt.id)}
          >
            <span className="theme-option-label">{opt.label}</span>
            <span className="theme-option-hint">{opt.hint}</span>
          </button>
        ))}
      </div>

      <h4 className="settings-section-title">{t("settings.language")}</h4>
      <p className="settings-hint">{t("settings.languageHint")}</p>
      <div className="locale-picker">
        {(["zh", "en"] as AppLocale[]).map((id) => (
          <button
            key={id}
            type="button"
            className={`locale-option${locale === id ? " active" : ""}`}
            onClick={() => onSelectLocale(id)}
          >
            {id === "zh" ? t("settings.langZh") : t("settings.langEn")}
          </button>
        ))}
      </div>

      <h4 className="settings-section-title">{t("settings.readingMode")}</h4>
      <p className="settings-hint">{t("settings.readingModeHint")}</p>
      <p className="settings-muted settings-analysis-note">
        {t("settings.readingModeNote", {
          mode: t(modeSettings.mode === "research" ? "mode.research" : "mode.advisor"),
          reading: t(
            modeSettings.readingMode === "professional"
              ? "settings.modeProfessional"
              : "settings.modeFriendly",
          ),
        })}
      </p>
      <div
        className="settings-tone-options"
        role="radiogroup"
        aria-label={t("settings.readingMode")}
      >
        {readingModeOptions.map((opt) => (
          <label
            key={opt.id}
            className={`locale-option${modeSettings.readingMode === opt.id ? " active" : ""}`}
          >
            <input
              type="radio"
              name="reading-mode-general"
              value={opt.id}
              checked={modeSettings.readingMode === opt.id}
              onChange={() => onSelectReadingMode(opt.id)}
            />
            <span className="theme-option-label">{t(opt.labelKey)}</span>
            <span className="theme-option-hint">{t(opt.hintKey)}</span>
          </label>
        ))}
      </div>

      <h4 className="settings-section-title">{t("settings.holdingsViewTitle")}</h4>
      <p className="settings-hint">{t("settings.holdingsViewHint")}</p>
      <div className="holdings-view-picker">
        {(["table", "cards"] as const).map((view) => (
          <button
            key={view}
            type="button"
            className={`holdings-view-option${modeSettings.holdingsView === view ? " active" : ""}`}
            onClick={() => onPersistModeSettings({ ...modeSettings, holdingsView: view })}
          >
            {view === "table" ? t("settings.holdingsViewTable") : t("settings.holdingsViewCards")}
          </button>
        ))}
      </div>

      <UsageStatsBlock />
    </>
  );
}
