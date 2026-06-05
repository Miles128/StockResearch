import { useEffect, useState } from "react";
import type { LlmSettingsMeta } from "./api";
import { ABOUT_INFO } from "./aboutInfo";
import { useI18n } from "./i18n";
import {
  loadLlmSettings,
  saveLlmSettings,
  type LlmUserSettings,
} from "./llmSettings";
import { api, type ResearchReportListItem } from "./api";
import {
  loadAnalysisSettings,
  saveAnalysisSettings,
  type AnalysisUserSettings,
} from "./analysisSettings";
import {
  loadDataSourceSettings,
  saveDataSourceSettings,
  type DataSourceUserSettings,
} from "./dataSourceSettings";
import {
  applyTheme,
  loadTheme,
  saveTheme,
  type AppTheme,
} from "./themeSettings";
import type { AppLocale } from "./localeSettings";

type SettingsTab = "general" | "data" | "llm" | "analysis" | "reports" | "about";

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
  required?: boolean;
  onConfigured?: () => void;
  /** inline = F5 设置页；modal = 首次配置弹层 */
  variant?: "inline" | "modal";
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
  variant = "modal",
}: SettingsPanelProps) {
  const { t, locale, setLocale } = useI18n();
  const [activeTab, setActiveTab] = useState<SettingsTab>(required ? "llm" : "general");
  const [meta, setMeta] = useState<LlmSettingsMeta | null>(null);
  const [form, setForm] = useState<LlmUserSettings>(loadLlmSettings);
  const [dataForm, setDataForm] = useState<DataSourceUserSettings>(loadDataSourceSettings);
  const [theme, setTheme] = useState<AppTheme>(loadTheme);
  const [analysis, setAnalysis] = useState<AnalysisUserSettings>(loadAnalysisSettings);
  const [error, setError] = useState("");
  const [testOk, setTestOk] = useState("");
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reports, setReports] = useState<ResearchReportListItem[]>([]);

  const tabs: { id: SettingsTab; label: string; hideWhenRequired?: boolean }[] = [
    { id: "general", label: t("settings.tabGeneral"), hideWhenRequired: true },
    { id: "data", label: t("settings.tabData"), hideWhenRequired: true },
    { id: "llm", label: t("settings.tabLlm") },
    { id: "analysis", label: t("settings.tabAnalysis"), hideWhenRequired: true },
    { id: "reports", label: t("settings.tabReports"), hideWhenRequired: true },
    { id: "about", label: t("settings.tabAbout"), hideWhenRequired: true },
  ];

  useEffect(() => {
    if (!open) return;
    setForm(loadLlmSettings());
    setDataForm(loadDataSourceSettings());
    setTheme(loadTheme());
    setAnalysis(loadAnalysisSettings());
    setError("");
    setTestOk("");
    if (required) setActiveTab("llm");
    api.llmSettings().then(setMeta).catch(() => setMeta(null));
    if (!required) {
      api.listReports().then(setReports).catch(() => setReports([]));
    }
  }, [open, required]);

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

  function saveDataSources() {
    saveDataSourceSettings(dataForm);
    setTestOk(t("settings.dataSaved"));
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
      if (!required && variant === "modal") onClose();
    } finally {
      setSaving(false);
    }
  }

  const busy = testing || saving;
  const themeOptions: { id: AppTheme; label: string; hint: string }[] = [
    { id: "orange-black", label: t("settings.themeOrange"), hint: t("settings.themeOrangeHint") },
    { id: "wine-red-white", label: t("settings.themeWine"), hint: t("settings.themeWineHint") },
  ];

  const visibleTabs = tabs.filter((tab) => !(required && tab.hideWhenRequired));

  const panelBody = (
    <div className={`settings-panel${variant === "inline" ? " settings-panel-inline" : ""}`}>
      <div className="settings-header">
        <h3 id="settings-title">{required ? t("settings.welcome") : t("settings.title")}</h3>
        {!required && variant === "modal" && (
          <button type="button" className="btn btn-ghost settings-close" onClick={onClose}>
            {t("settings.close")}
          </button>
        )}
      </div>

      {required && <p className="settings-required-banner">{t("settings.requiredBanner")}</p>}

      {!required && (
        <nav className="settings-tabs" aria-label={t("settings.tabsAria")}>
          {visibleTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`settings-tab${activeTab === tab.id ? " active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      )}

      <div className="settings-tab-body">
        {!required && activeTab === "general" && (
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

        {!required && activeTab === "data" && (
          <>
            <h4 className="settings-section-title">{t("settings.tushareTitle")}</h4>
            <p className="settings-hint">{t("settings.tushareHint")}</p>
            <label className="settings-field">
              <span>{t("settings.tushareToken")}</span>
              <input
                type="password"
                autoComplete="off"
                value={dataForm.tushareToken}
                onChange={(e) => setDataForm((f) => ({ ...f, tushareToken: e.target.value }))}
              />
            </label>
            <p className="settings-muted">{t("settings.tushareNote")}</p>
            <div className="settings-actions settings-actions-left">
              <button type="button" className="btn btn-primary" onClick={saveDataSources}>
                {t("settings.dataSave")}
              </button>
            </div>
          </>
        )}

        {(required || activeTab === "llm") && (
          <>
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
              {!required && variant === "modal" && (
                <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>
                  {t("settings.cancel")}
                </button>
              )}
              <button type="button" className="btn btn-ghost" onClick={handleTest} disabled={busy}>
                {testing ? t("settings.testing") : t("settings.test")}
              </button>
              <button type="button" className="btn btn-primary" onClick={handleSave} disabled={busy}>
                {saving ? t("settings.saving") : required ? t("settings.saveEnter") : t("settings.save")}
              </button>
            </div>
          </>
        )}

        {!required && activeTab === "analysis" && (
          <>
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
          </>
        )}

        {!required && activeTab === "reports" && (
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
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => api.downloadReportMarkdown(r.id)}
                    >
                      {t("settings.reportExport")}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}

        {!required && activeTab === "about" && (
          <div className="about-panel about-panel-inline">
            <p className="about-product">{ABOUT_INFO.product}</p>
            <p className="settings-hint">{t("about.tagline")}</p>
            <dl className="about-dl">
              <dt>{t("about.author")}</dt>
              <dd>{ABOUT_INFO.author}</dd>
              <dt>GitHub</dt>
              <dd>
                <a href={ABOUT_INFO.repoUrl} target="_blank" rel="noopener noreferrer">
                  {ABOUT_INFO.repoUrl}
                </a>
              </dd>
              <dt>{t("about.email")}</dt>
              <dd>
                <a href={`mailto:${ABOUT_INFO.email}`}>{ABOUT_INFO.email}</a>
              </dd>
              <dt>{t("about.xiaohongshu")}</dt>
              <dd>
                <a href={ABOUT_INFO.xiaohongshuUrl} target="_blank" rel="noopener noreferrer">
                  {ABOUT_INFO.xiaohongshuId}
                </a>
              </dd>
            </dl>
            <h4 className="about-section-title">{t("about.refs")}</h4>
            <ul className="about-ref-list">
              {ABOUT_INFO.references.map((ref) => (
                <li key={ref.url}>
                  <a href={ref.url} target="_blank" rel="noopener noreferrer">
                    {ref.name}
                  </a>
                  {ref.note && <span className="about-ref-note"> — {ref.note}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );

  if (variant === "inline") {
    return panelBody;
  }

  return (
    <div
      className={`settings-overlay${required ? " settings-overlay-required" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
    >
      {!required && <div className="settings-backdrop" onClick={onClose} />}
      {required && <div className="settings-backdrop settings-backdrop-lock" />}
      {panelBody}
    </div>
  );
}
