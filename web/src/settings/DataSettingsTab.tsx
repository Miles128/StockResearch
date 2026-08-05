import { useState } from "react";
import type { DataSourceUserSettings } from "../dataSourceSettings";
import type { ModeSettings } from "../modeSettings";
import { api, type DiagnosticsItem, type DiagnosticsResult } from "../api";
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
  const [diagRunning, setDiagRunning] = useState(false);
  const [diag, setDiag] = useState<DiagnosticsResult | null>(null);
  const [diagError, setDiagError] = useState<string | null>(null);

  const runDiagnostics = async () => {
    setDiagRunning(true);
    setDiagError(null);
    try {
      const result = await api.runDiagnostics();
      setDiag(result);
    } catch (err) {
      setDiagError(err instanceof Error ? err.message : String(err));
    } finally {
      setDiagRunning(false);
    }
  };

  const renderDiagItem = (item: DiagnosticsItem) => (
    <div key={item.key} className={`diag-item${item.ok ? " diag-ok" : " diag-fail"}`}>
      <span className="diag-label">{item.label}</span>
      <span className="diag-detail">
        {item.detail}
        {item.hint ? <span className="diag-hint">（{item.hint}）</span> : null}
      </span>
    </div>
  );

  return (
    <>
      <h4 className="settings-section-title">{t("settings.quoteCacheTitle")}</h4>
      <p className="settings-hint">{t("settings.quoteCacheHint")}</p>
      <label className="settings-field">
        <span>
          {t("settings.quoteRefreshMinutes")} <strong>{modeSettings.quoteRefreshMinutes}</strong>
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
          onChange={(e) => onDataFormChange({ ...dataForm, tushareToken: e.target.value })}
        />
      </label>
      <p className="settings-muted">{t("settings.tushareNote")}</p>

      <div className="tushare-guide">
        <h5 className="tushare-guide-title">{t("settings.tushareGuideTitle")}</h5>
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

      <h4 className="settings-section-title">{t("settings.diagnosticsTitle")}</h4>
      <p className="settings-hint">{t("settings.diagnosticsHint")}</p>
      <div className="settings-actions settings-actions-left">
        <button
          type="button"
          className="btn btn-ghost"
          onClick={runDiagnostics}
          disabled={diagRunning}
        >
          {diagRunning ? t("settings.diagnosticsBusy") : t("settings.diagnosticsRun")}
        </button>
      </div>
      {diagError ? <p className="settings-muted diag-error">{diagError}</p> : null}
      {diag ? (
        <div className="diag-block">
          {renderDiagItem(diag.llm)}
          {diag.providers.map(renderDiagItem)}
          {diag.env.map(renderDiagItem)}
        </div>
      ) : null}

      <h4 className="settings-section-title">{t("settings.bochaTitle")}</h4>
      <p className="settings-hint">{t("settings.bochaHint")}</p>
      <label className="settings-field">
        <span>{t("settings.bochaApiKey")}</span>
        <input
          type="password"
          autoComplete="off"
          value={dataForm.bochaApiKey}
          onChange={(e) => onDataFormChange({ ...dataForm, bochaApiKey: e.target.value })}
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
