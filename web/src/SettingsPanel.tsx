import { useEffect, useState } from "react";
import type { LlmSettingsMeta } from "./api";
import { useI18n } from "./i18n";
import {
  loadLlmSettings,
  saveLlmSettings,
  type LlmUserSettings,
} from "./llmSettings";
import { api } from "./api";
import {
  loadAnalysisSettings,
  saveAnalysisSettings,
  type AnalysisUserSettings,
} from "./analysisSettings";
import {
  applyTheme,
  loadTheme,
  saveTheme,
  type AppTheme,
} from "./themeSettings";
import type { AppLocale } from "./localeSettings";

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
  /** 首次使用：必须完成大模型配置才能进入应用 */
  required?: boolean;
  onConfigured?: () => void;
}

function formatApiError(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export function SettingsPanel({
  open,
  onClose,
  required = false,
  onConfigured,
}: SettingsPanelProps) {
  const { t, locale, setLocale } = useI18n();
  const [meta, setMeta] = useState<LlmSettingsMeta | null>(null);
  const [form, setForm] = useState<LlmUserSettings>(loadLlmSettings);
  const [theme, setTheme] = useState<AppTheme>(loadTheme);
  const [analysis, setAnalysis] = useState<AnalysisUserSettings>(loadAnalysisSettings);
  const [error, setError] = useState("");
  const [testOk, setTestOk] = useState("");
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(loadLlmSettings());
    setTheme(loadTheme());
    setAnalysis(loadAnalysisSettings());
    setError("");
    setTestOk("");
    api.llmSettings().then(setMeta).catch(() => setMeta(null));
  }, [open]);

  if (!open) return null;

  function selectTheme(next: AppTheme) {
    setTheme(next);
    saveTheme(next);
    applyTheme(next);
  }

  function selectLocale(next: AppLocale) {
    setLocale(next);
  }

  function toggleDebate(enabled: boolean) {
    const next = { ...analysis, enableDebate: enabled };
    setAnalysis(next);
    saveAnalysisSettings(next);
  }

  async function testConnection(): Promise<boolean> {
    setError("");
    setTestOk("");
    const urlUsed = form.baseUrl.trim();
    try {
      const result = await api.testLlmConnection(form);
      setTestOk(result.message);
      return true;
    } catch (e) {
      const msg = formatApiError(e);
      setError(urlUsed ? `${msg}（表单 URL：${urlUsed}）` : msg);
      return false;
    }
  }

  async function handleTest() {
    setTesting(true);
    try {
      await testConnection();
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    try {
      if (!(await testConnection())) return;
      saveLlmSettings(form);
      onConfigured?.();
      if (!required) onClose();
    } finally {
      setSaving(false);
    }
  }

  const busy = testing || saving;
  const themeOptions: { id: AppTheme; label: string; hint: string }[] = [
    { id: "orange-black", label: t("settings.themeOrange"), hint: t("settings.themeOrangeHint") },
    { id: "wine-red-white", label: t("settings.themeWine"), hint: t("settings.themeWineHint") },
  ];

  return (
    <div
      className={`settings-overlay${required ? " settings-overlay-required" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
    >
      {!required && <div className="settings-backdrop" onClick={onClose} />}
      {required && <div className="settings-backdrop settings-backdrop-lock" />}
      <div className="settings-panel">
        <div className="settings-header">
          <h3 id="settings-title">{required ? t("settings.welcome") : t("settings.title")}</h3>
          {!required && (
            <button type="button" className="btn btn-ghost settings-close" onClick={onClose}>
              {t("settings.close")}
            </button>
          )}
        </div>

        {required && (
          <p className="settings-required-banner">{t("settings.requiredBanner")}</p>
        )}

        {!required && (
          <>
            <h4 className="settings-section-title">{t("settings.appearance")}</h4>
            <p className="settings-hint">{t("settings.appearanceHint")}</p>
            <div className="theme-picker">
              {themeOptions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  className={`theme-option${theme === opt.id ? " active" : ""}`}
                  data-theme-preview={opt.id}
                  onClick={() => selectTheme(opt.id)}
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
                  onClick={() => selectLocale(id)}
                >
                  {id === "zh" ? t("settings.langZh") : t("settings.langEn")}
                </button>
              ))}
            </div>

          </>
        )}

        <h4 className="settings-section-title">{t("settings.analysis")}</h4>
        <p className="settings-hint">{t("settings.analysisHint")}</p>
        <label className="settings-check">
          <input
            type="checkbox"
            checked={analysis.enableDebate}
            onChange={(e) => toggleDebate(e.target.checked)}
          />
          <span>{t("settings.enableDebate")}</span>
        </label>
        <p className="settings-muted settings-analysis-note">
          {analysis.enableDebate ? t("settings.debateOnNote") : t("settings.debateOffNote")}
        </p>

        <h4 className="settings-section-title">{t("settings.llm")}</h4>
        <p className="settings-hint">{t("settings.llmHint")}</p>

        {error && <p className="settings-error">{error}</p>}
        {testOk && !error && <p className="settings-ok">{testOk}</p>}

        <label className="settings-field">
          <span>{t("settings.apiKey")}</span>
          <input
            type="password"
            autoComplete="off"
            value={form.apiKey}
            disabled={form.useMock}
            onChange={(e) => setForm((f) => ({ ...f, apiKey: e.target.value }))}
          />
        </label>

        <label className="settings-field">
          <span>{t("settings.baseUrl")}</span>
          <input
            type="text"
            autoComplete="off"
            spellCheck={false}
            value={form.baseUrl}
            disabled={form.useMock}
            onChange={(e) => setForm((f) => ({ ...f, baseUrl: e.target.value }))}
          />
        </label>

        <label className="settings-field">
          <span>{t("settings.model")}</span>
          <input
            type="text"
            value={form.model}
            disabled={form.useMock}
            onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
          />
        </label>

        <label className="settings-field">
          <span>
            {t("settings.temperature")} <strong>{form.temperature.toFixed(1)}</strong>
            <span className="settings-muted">{t("settings.tempHint")}</span>
          </span>
          <input
            type="range"
            min={0}
            max={2}
            step={0.1}
            value={form.temperature}
            onChange={(e) =>
              setForm((f) => ({ ...f, temperature: parseFloat(e.target.value) }))
            }
          />
        </label>

        <label className="settings-check">
          <input
            type="checkbox"
            checked={form.useMock}
            onChange={(e) => setForm((f) => ({ ...f, useMock: e.target.checked }))}
          />
          <span>{t("settings.useMock")}</span>
        </label>

        {meta?.server_use_mock && !required && (
          <p className="settings-warn">{t("settings.serverMock")}</p>
        )}

        <div className="settings-actions">
          {!required && (
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>
              {t("settings.cancel")}
            </button>
          )}
          <button
            type="button"
            className="btn btn-ghost"
            onClick={handleTest}
            disabled={busy}
          >
            {testing ? t("settings.testing") : t("settings.test")}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSave}
            disabled={busy}
          >
            {saving ? t("settings.saving") : required ? t("settings.saveEnter") : t("settings.save")}
          </button>
        </div>
      </div>
    </div>
  );
}
