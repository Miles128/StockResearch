import type { DataSourceUserSettings } from "../dataSourceSettings";
import type { ModeSettings } from "../modeSettings";
import { useI18n } from "../i18n";
import { TushareStatusBadge } from "./TushareStatusBadge";

interface DataSettingsTabProps {
  modeSettings: ModeSettings;
  dataForm: DataSourceUserSettings;
  onPersistModeSettings: (next: ModeSettings) => void;
  onDataFormChange: (next: DataSourceUserSettings) => void;
  onSave: () => void;
}

export function DataSettingsTab({
  modeSettings,
  dataForm,
  onPersistModeSettings,
  onDataFormChange,
  onSave,
}: DataSettingsTabProps) {
  const { t } = useI18n();

  return (
    <>
      <h4 className="settings-section-title">
        {t("settings.quoteCacheTitle")}
      </h4>
      <p className="settings-hint">{t("settings.quoteCacheHint")}</p>
      <label className="settings-field">
        <span>
          {t("settings.quoteRefreshMinutes")}{" "}
          <strong>{modeSettings.quoteRefreshMinutes}</strong>
        </span>
        <input
          type="range"
          min={1}
          max={120}
          step={1}
          value={modeSettings.quoteRefreshMinutes}
          onChange={(e) =>
            onPersistModeSettings({
              ...modeSettings,
              quoteRefreshMinutes: parseInt(e.target.value, 10),
            })
          }
        />
      </label>
      <p className="settings-muted settings-analysis-note">
        {t("settings.quoteRefreshNote", {
          minutes: String(modeSettings.quoteRefreshMinutes),
        })}
      </p>

      <h4 className="settings-section-title">{t("settings.tushareTitle")}</h4>
      <p className="settings-hint">{t("settings.tushareHint")}</p>
      <label className="settings-field">
        <span>{t("settings.tushareToken")}</span>
        <input
          type="password"
          autoComplete="off"
          value={dataForm.tushareToken}
          onChange={(e) =>
            onDataFormChange({ ...dataForm, tushareToken: e.target.value })
          }
        />
      </label>
      <p className="settings-muted">{t("settings.tushareNote")}</p>

      <div className="tushare-guide">
        <h5 className="tushare-guide-title">
          {t("settings.tushareGuideTitle")}
        </h5>
        <ol className="tushare-guide-steps">
          <li>{t("settings.tushareGuideStep1")}</li>
          <li>{t("settings.tushareGuideStep2")}</li>
          <li>{t("settings.tushareGuideStep3")}</li>
          <li>{t("settings.tushareGuideStep4")}</li>
        </ol>
        <a
          className="tushare-guide-link"
          href="https://tushare.pro/register?src=stockresearch"
          target="_blank"
          rel="noreferrer noopener"
        >
          {t("settings.tushareRegisterLink")} ↗
        </a>
      </div>

      <TushareStatusBadge />

      <h4 className="settings-section-title">{t("settings.bochaTitle")}</h4>
      <p className="settings-hint">{t("settings.bochaHint")}</p>
      <label className="settings-field">
        <span>{t("settings.bochaApiKey")}</span>
        <input
          type="password"
          autoComplete="off"
          value={dataForm.bochaApiKey}
          onChange={(e) =>
            onDataFormChange({ ...dataForm, bochaApiKey: e.target.value })
          }
        />
      </label>
      <p className="settings-muted">{t("settings.bochaNote")}</p>
      <a
        className="tushare-guide-link"
        href="https://open.bochaai.com"
        target="_blank"
        rel="noreferrer noopener"
      >
        {t("settings.bochaRegisterLink")} ↗
      </a>

      <div className="settings-actions settings-actions-left">
        <button type="button" className="btn btn-primary" onClick={onSave}>
          {t("settings.dataSave")}
        </button>
      </div>
    </>
  );
}
