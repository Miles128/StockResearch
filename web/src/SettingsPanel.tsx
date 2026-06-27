import { useEffect, useState } from "react";
import type { LlmSettingsMeta } from "./api";
import { ABOUT_INFO } from "./aboutInfo";
import { useI18n } from "./i18n";
import {
  llmMetaToForm,
  loadLlmSettings,
  saveLlmSettings,
  type LlmUserSettings,
} from "./llmSettings";
import {
  api,
  type MemorySearchResult,
  type ResearchReportListItem,
  type SignalBacktest,
} from "./api";
import {
  BUILTIN_MASTER_IDS,
  loadModeSettings,
  modeSettingsToApiPayload,
  saveModeSettings,
  type AppMode,
  type CustomMaster,
  type ModeSettings,
  type ReadingMode,
} from "./modeSettings";
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
  onModeSettingsChange?: (settings: ModeSettings) => void;
  /** inline = F5 设置页；modal = 首次配置弹层 */
  variant?: "inline" | "modal";
}

function formatApiError(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

type TushareState = "checking" | "ok" | "no_token" | "unavailable";

function TushareStatusBadge() {
  const { t } = useI18n();
  const [state, setState] = useState<TushareState>("checking");

  useEffect(() => {
    let alive = true;
    api
      .dataSourceStatus()
      .then((status) => {
        if (!alive) return;
        if (status.tushare_configured && status.tushare_available) setState("ok");
        else if (!status.tushare_configured) setState("no_token");
        else setState("unavailable");
      })
      .catch(() => {
        if (alive) setState("unavailable");
      });
    return () => {
      alive = false;
    };
  }, []);

  const text =
    state === "checking"
      ? t("settings.tushareStatusChecking")
      : state === "ok"
        ? t("settings.tushareStatusOk")
        : state === "no_token"
          ? t("settings.tushareStatusNoToken")
          : t("settings.tushareStatusUnavailable");

  return <p className={`tushare-status tushare-status-${state}`}>{text}</p>;
}

export function SettingsPanel({
  open,
  onClose,
  required = false,
  onConfigured,
  onModeSettingsChange,
  variant = "modal",
}: SettingsPanelProps) {
  const { t, locale, setLocale } = useI18n();
  const [activeTab, setActiveTab] = useState<SettingsTab>(required ? "llm" : "general");
  const [meta, setMeta] = useState<LlmSettingsMeta | null>(null);
  const [form, setForm] = useState<LlmUserSettings>(loadLlmSettings);
  const [dataForm, setDataForm] = useState<DataSourceUserSettings>(loadDataSourceSettings);
  const [theme, setTheme] = useState<AppTheme>(loadTheme);
  const [modeSettingsState, setModeSettingsState] = useState<ModeSettings>(loadModeSettings);
  const [error, setError] = useState("");
  const [testOk, setTestOk] = useState("");
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reports, setReports] = useState<ResearchReportListItem[]>([]);
  const [backtest, setBacktest] = useState<SignalBacktest | null>(null);
  const [memoryQuery, setMemoryQuery] = useState("");
  const [memoryHits, setMemoryHits] = useState<MemorySearchResult | null>(null);

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
    setModeSettingsState(loadModeSettings());
    setError("");
    setTestOk("");
    if (required) setActiveTab("llm");
    api
      .llmSettings()
      .then((m) => {
        setMeta(m);
        const fromServer = llmMetaToForm(m);
        const local = loadLlmSettings();
        const hasLocal =
          local.apiKey.trim() || local.baseUrl.trim() || local.model.trim() || local.useMock;
        setForm(hasLocal ? local : fromServer);
      })
      .catch(() => {
        setMeta(null);
        setForm(loadLlmSettings());
      });
    if (!required) {
      api.listReports().then(setReports).catch(() => setReports([]));
      api.signalBacktest().then(setBacktest).catch(() => setBacktest(null));
      setMemoryHits(null);
      setMemoryQuery("");
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

  function persistModeSettings(next: ModeSettings) {
    setModeSettingsState(next);
    saveModeSettings(next);
    void api.saveModeSettings(modeSettingsToApiPayload(next)).catch(() => {});
    onModeSettingsChange?.(next);
  }

  function toggleDebate(enabled: boolean) {
    persistModeSettings({ ...modeSettingsState, enableDebate: enabled });
  }

  function toggleMasterCommentary(enabled: boolean) {
    persistModeSettings({ ...modeSettingsState, enableMasterCommentary: enabled });
  }

  function toggleMasterSelection(masterId: string, enabled: boolean) {
    const selected = new Set(modeSettingsState.selectedMasters);
    if (enabled) selected.add(masterId);
    else selected.delete(masterId);
    persistModeSettings({
      ...modeSettingsState,
      selectedMasters: Array.from(selected),
    });
  }

  function addCustomMaster() {
    const id = window.prompt(t("settings.customMasterIdPrompt"), "my_master");
    if (!id) return;
    const name = window.prompt(t("settings.customMasterNamePrompt"), id);
    if (!name) return;
    const systemPrompt = window.prompt(t("settings.customMasterPromptPrompt"), "");
    if (!systemPrompt || systemPrompt.trim().length < 10) return;
    const next: CustomMaster = {
      id: id.trim().toLowerCase(),
      name: name.trim(),
      systemPrompt: systemPrompt.trim(),
    };
    persistModeSettings({
      ...modeSettingsState,
      customMasters: [...modeSettingsState.customMasters, next],
      selectedMasters: [...modeSettingsState.selectedMasters, next.id],
    });
  }

  function removeCustomMaster(masterId: string) {
    persistModeSettings({
      ...modeSettingsState,
      customMasters: modeSettingsState.customMasters.filter((m) => m.id !== masterId),
      selectedMasters: modeSettingsState.selectedMasters.filter((id) => id !== masterId),
    });
  }

  function selectReadingMode(readingMode: ReadingMode) {
    persistModeSettings({ ...modeSettingsState, readingMode });
  }

  const readingModeOptions: { id: ReadingMode; labelKey: string; hintKey: string }[] = [
    { id: "professional", labelKey: "settings.modeProfessional", hintKey: "settings.modeProfessionalHint" },
    { id: "friendly", labelKey: "settings.modeFriendly", hintKey: "settings.modeFriendlyHint" },
  ];

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
      const saved = await api.saveLlmSettings(form);
      setMeta(saved);
      saveLlmSettings(form);
      setTestOk(t("settings.savedEnv"));
      onConfigured?.();
      if (!required && variant === "modal") onClose();
    } catch (e) {
      setError(formatApiError(e));
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

            <h4 className="settings-section-title">{t("settings.bochaTitle")}</h4>
            <p className="settings-hint">{t("settings.bochaHint")}</p>
            <label className="settings-field">
              <span>{t("settings.bochaApiKey")}</span>
              <input
                type="password"
                autoComplete="off"
                value={dataForm.bochaApiKey}
                onChange={(e) => setDataForm((f) => ({ ...f, bochaApiKey: e.target.value }))}
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
                checked={modeSettingsState.enableDebate}
                onChange={(e) => toggleDebate(e.target.checked)}
              />
              <span>{t("settings.enableDebate")}</span>
            </label>
            <p className="settings-muted settings-analysis-note">
              {modeSettingsState.enableDebate ? t("settings.debateOnNote") : t("settings.debateOffNote")}
            </p>

            <label className="settings-check">
              <input
                type="checkbox"
                checked={modeSettingsState.enableMasterCommentary}
                onChange={(e) => toggleMasterCommentary(e.target.checked)}
              />
              <span>{t("settings.enableMasterCommentary")}</span>
            </label>
            <p className="settings-muted settings-analysis-note">
              {modeSettingsState.enableMasterCommentary
                ? t("settings.masterCommentaryOnNote")
                : t("settings.masterCommentaryOffNote")}
            </p>

            <h4 className="settings-section-title">{t("settings.masterSelection")}</h4>
            <p className="settings-hint">{t("settings.masterSelectionHint")}</p>
            <div className="settings-master-list">
              {BUILTIN_MASTER_IDS.map((id) => (
                <label key={id} className="settings-check">
                  <input
                    type="checkbox"
                    checked={modeSettingsState.selectedMasters.includes(id)}
                    onChange={(e) => toggleMasterSelection(id, e.target.checked)}
                    disabled={!modeSettingsState.enableMasterCommentary}
                  />
                  <span>{t(`settings.master.${id}`)}</span>
                </label>
              ))}
              {modeSettingsState.customMasters.map((master) => (
                <label key={master.id} className="settings-check settings-custom-master-row">
                  <input
                    type="checkbox"
                    checked={modeSettingsState.selectedMasters.includes(master.id)}
                    onChange={(e) => toggleMasterSelection(master.id, e.target.checked)}
                    disabled={!modeSettingsState.enableMasterCommentary}
                  />
                  <span>{master.name}</span>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => removeCustomMaster(master.id)}
                  >
                    {t("settings.removeCustomMaster")}
                  </button>
                </label>
              ))}
            </div>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={addCustomMaster}
              disabled={!modeSettingsState.enableMasterCommentary}
            >
              {t("settings.addCustomMaster")}
            </button>

            <h4 className="settings-section-title">{t("settings.readingMode")}</h4>
            <p className="settings-hint">{t("settings.readingModeHint")}</p>
            <p className="settings-muted settings-analysis-note">
              {t("settings.readingModeNote", {
                mode: t(modeSettingsState.mode === "research" ? "mode.research" : "mode.advisor"),
                reading: t(
                  modeSettingsState.readingMode === "professional"
                    ? "settings.modeProfessional"
                    : "settings.modeFriendly",
                ),
              })}
              {modeSettingsState.mode === "advisor"
                ? ` · ${t("settings.readingModePersonal")}`
                : ` · ${t("settings.readingModeExpert")}`}
            </p>
            <div className="settings-tone-options" role="radiogroup" aria-label={t("settings.readingMode")}>
              {readingModeOptions.map((opt) => (
                <label
                  key={opt.id}
                  className={`locale-option${modeSettingsState.readingMode === opt.id ? " active" : ""}`}
                >
                  <input
                    type="radio"
                    name="reading-mode"
                    value={opt.id}
                    checked={modeSettingsState.readingMode === opt.id}
                    onChange={() => selectReadingMode(opt.id)}
                  />
                  <span className="theme-option-label">{t(opt.labelKey)}</span>
                  <span className="theme-option-hint">{t(opt.hintKey)}</span>
                </label>
              ))}
            </div>
            {locale === "en" && (
              <p className="settings-muted settings-analysis-note">{t("settings.outputLocaleEnNote")}</p>
            )}
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
            {backtest && backtest.horizons.some((h) => h.sample_count > 0) ? (
              <ul className="report-history-list">
                {backtest.horizons.map((h) => (
                  <li key={h.days} className="settings-muted">
                    {t("settings.signalBacktestRow", {
                      days: String(h.days),
                      n: String(h.sample_count),
                      bull:
                        h.bullish_avg_return_pct != null ? String(h.bullish_avg_return_pct) : "—",
                      bear:
                        h.bearish_avg_return_pct != null ? String(h.bearish_avg_return_pct) : "—",
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
                onChange={(e) => setMemoryQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && memoryQuery.trim()) {
                    void api.searchMemory(memoryQuery.trim()).then(setMemoryHits);
                  }
                }}
              />
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={!memoryQuery.trim()}
                onClick={() => void api.searchMemory(memoryQuery.trim()).then(setMemoryHits)}
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
