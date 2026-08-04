import { useEffect, useState } from "react";
import type { LlmSettingsMeta } from "./api";
import { useI18n } from "./i18n";
import {
  llmMetaToForm,
  loadLlmSettings,
  saveLlmSettings,
  type LlmUserSettings,
} from "./llmSettings";
import {
  api,
  type GlossaryTerm,
  type MemorySearchResult,
  type ResearchReportListItem,
  type SignalBacktest,
  PriceAlertSettings,
} from "./api";
import {
  loadModeSettings,
  modeSettingsToApiPayload,
  saveModeSettings,
  type CustomGlossaryTerm,
  type CustomMaster,
  type AnalysisDepth,
  type ModeSettings,
  type ReadingMode,
} from "./modeSettings";
import {
  loadDataSourceSettings,
  saveDataSourceSettings,
  type DataSourceUserSettings,
} from "./dataSourceSettings";
import { applyTheme, loadTheme, saveTheme, type AppTheme } from "./themeSettings";
import type { AppLocale } from "./localeSettings";
import { AboutSettingsTab } from "./settings/AboutSettingsTab";
import { AnalysisSettingsTab } from "./settings/AnalysisSettingsTab";
import { GlossarySettingsTab } from "./settings/GlossarySettingsTab";
import { DataSettingsTab } from "./settings/DataSettingsTab";
import { GeneralSettingsTab } from "./settings/GeneralSettingsTab";
import { LlmSettingsTab } from "./settings/LlmSettingsTab";
import { ReportsSettingsTab } from "./settings/ReportsSettingsTab";
import { formatApiError } from "./settings/formatApiError";

type SettingsTab = "general" | "data" | "llm" | "analysis" | "glossary" | "reports" | "about";

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
  required?: boolean;
  onConfigured?: () => void;
  onModeSettingsChange?: (settings: ModeSettings) => void;
  /** inline = 设置页内嵌；modal = 首次配置弹层 */
  variant?: "inline" | "modal";
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
  const [glossaryTerms, setGlossaryTerms] = useState<GlossaryTerm[]>([]);
  const [glossaryFilter, setGlossaryFilter] = useState("");
  const [newGlossaryShort, setNewGlossaryShort] = useState("");
  const [newGlossaryDef, setNewGlossaryDef] = useState("");
  const [newGlossaryAnalogy, setNewGlossaryAnalogy] = useState("");
  const [priceAlertSettings, setPriceAlertSettings] = useState<PriceAlertSettings | null>(null);

  const tabs: { id: SettingsTab; label: string; hideWhenRequired?: boolean }[] = [
    {
      id: "general",
      label: t("settings.tabGeneral"),
      hideWhenRequired: true,
    },
    { id: "data", label: t("settings.tabData"), hideWhenRequired: true },
    { id: "llm", label: t("settings.tabLlm") },
    {
      id: "analysis",
      label: t("settings.tabAnalysis"),
      hideWhenRequired: true,
    },
    {
      id: "glossary",
      label: t("settings.tabGlossary"),
      hideWhenRequired: true,
    },
    {
      id: "reports",
      label: t("settings.tabReports"),
      hideWhenRequired: true,
    },
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
      api
        .listReports()
        .then(setReports)
        .catch(() => setReports([]));
      api
        .signalBacktest()
        .then(setBacktest)
        .catch(() => setBacktest(null));
      api
        .priceAlertSettings()
        .then(setPriceAlertSettings)
        .catch(() => setPriceAlertSettings(null));
      setMemoryHits(null);
      setMemoryQuery("");
    }
  }, [open, required]);

  useEffect(() => {
    if (!open || (activeTab !== "glossary" && activeTab !== "analysis")) return;
    api
      .glossary()
      .then(setGlossaryTerms)
      .catch(() => setGlossaryTerms([]));
  }, [open, activeTab, modeSettingsState.customGlossary]);

  if (!open) return null;

  function toggleUiPolling(enabled: boolean) {
    if (enabled && !window.confirm(t("settings.uiPollingConfirm"))) return;
    persistModeSettings({ ...modeSettingsState, uiPollingEnabled: enabled });
  }

  async function togglePriceAlerts(enabled: boolean) {
    try {
      const updated = await api.updatePriceAlertSettings({ enabled });
      setPriceAlertSettings(updated);
    } catch (e) {
      setError(formatApiError(e));
    }
  }

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
    persistModeSettings({
      ...modeSettingsState,
      enableMasterCommentary: enabled,
    });
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

  function addCustomGlossaryTerm() {
    const short = newGlossaryShort.trim();
    const def = newGlossaryDef.trim();
    if (!short || def.length < 2) return;
    const id = short.slice(0, 32);
    if (modeSettingsState.customGlossary.some((term) => term.id === id)) return;
    const nextTerm: CustomGlossaryTerm = {
      id,
      short,
      def,
      analogy: newGlossaryAnalogy.trim() || undefined,
    };
    persistModeSettings({
      ...modeSettingsState,
      customGlossary: [...modeSettingsState.customGlossary, nextTerm],
    });
    setNewGlossaryShort("");
    setNewGlossaryDef("");
    setNewGlossaryAnalogy("");
  }

  function removeCustomGlossaryTerm(termId: string) {
    persistModeSettings({
      ...modeSettingsState,
      customGlossary: modeSettingsState.customGlossary.filter((term) => term.id !== termId),
    });
  }

  function selectReadingMode(readingMode: ReadingMode) {
    persistModeSettings({ ...modeSettingsState, readingMode });
  }

  function selectAnalysisDepth(analysisDepth: AnalysisDepth) {
    persistModeSettings({ ...modeSettingsState, analysisDepth });
  }

  const readingModeOptions: {
    id: ReadingMode;
    labelKey: string;
    hintKey: string;
  }[] = [
    {
      id: "friendly",
      labelKey: "settings.modeFriendly",
      hintKey: "settings.modeFriendlyHint",
    },
    {
      id: "standard",
      labelKey: "settings.modeStandard",
      hintKey: "settings.modeStandardHint",
    },
    {
      id: "professional",
      labelKey: "settings.modeProfessional",
      hintKey: "settings.modeProfessionalHint",
    },
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
    {
      id: "institutional-light",
      label: t("settings.themeLight"),
      hint: t("settings.themeLightHint"),
    },
    {
      id: "institutional-dark",
      label: t("settings.themeDark"),
      hint: t("settings.themeDarkHint"),
    },
  ];

  const visibleTabs = tabs.filter((tab) => !(required && tab.hideWhenRequired));

  const panelBody = (
    <div
      className={`settings-panel settings-panel-v2${variant === "inline" ? " settings-panel-inline" : ""}`}
    >
      <div className="settings-header">
        <div>
          <h3 id="settings-title">{required ? t("settings.welcome") : t("settings.title")}</h3>
          {!required && <p className="settings-header-sub">{t("settings.subtitle")}</p>}
        </div>
        {!required && variant === "modal" && (
          <button type="button" className="btn btn-ghost settings-close" onClick={onClose}>
            {t("settings.close")}
          </button>
        )}
      </div>

      {required && <p className="settings-required-banner">{t("settings.requiredBanner")}</p>}

      <div className={`settings-body${required ? " settings-body-single" : ""}`}>
        {!required && (
          <nav className="settings-sidebar" aria-label={t("settings.tabsAria")}>
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

        <div className="settings-content">
          <div className="settings-tab-body">
            {!required && activeTab === "general" && (
              <GeneralSettingsTab
                modeSettings={modeSettingsState}
                priceAlertSettings={priceAlertSettings}
                theme={theme}
                themeOptions={themeOptions}
                readingModeOptions={readingModeOptions}
                onPersistModeSettings={persistModeSettings}
                onTogglePriceAlerts={togglePriceAlerts}
                onToggleUiPolling={toggleUiPolling}
                onSelectTheme={selectTheme}
                onSelectLocale={selectLocale}
                onSelectReadingMode={selectReadingMode}
              />
            )}

            {!required && activeTab === "data" && (
              <DataSettingsTab
                modeSettings={modeSettingsState}
                dataForm={dataForm}
                onPersistModeSettings={persistModeSettings}
                onDataFormChange={setDataForm}
                onSave={saveDataSources}
              />
            )}

            {(required || activeTab === "llm") && (
              <LlmSettingsTab
                required={required}
                variant={variant}
                form={form}
                meta={meta}
                error={error}
                testOk={testOk}
                busy={busy}
                testing={testing}
                saving={saving}
                onFormChange={setForm}
                onClose={onClose}
                onTest={handleTest}
                onSave={handleSave}
              />
            )}

            {!required && activeTab === "analysis" && (
              <AnalysisSettingsTab
                modeSettings={modeSettingsState}
                onToggleDebate={toggleDebate}
                onSelectAnalysisDepth={selectAnalysisDepth}
                onToggleMasterCommentary={toggleMasterCommentary}
                onToggleMasterSelection={toggleMasterSelection}
                onAddCustomMaster={addCustomMaster}
                onRemoveCustomMaster={removeCustomMaster}
              />
            )}

            {!required && activeTab === "glossary" && (
              <GlossarySettingsTab
                modeSettings={modeSettingsState}
                glossaryTerms={glossaryTerms}
                glossaryFilter={glossaryFilter}
                newGlossaryShort={newGlossaryShort}
                newGlossaryDef={newGlossaryDef}
                newGlossaryAnalogy={newGlossaryAnalogy}
                onGlossaryFilterChange={setGlossaryFilter}
                onNewGlossaryShortChange={setNewGlossaryShort}
                onNewGlossaryDefChange={setNewGlossaryDef}
                onNewGlossaryAnalogyChange={setNewGlossaryAnalogy}
                onPersistModeSettings={persistModeSettings}
                onAddCustomGlossaryTerm={addCustomGlossaryTerm}
                onRemoveCustomGlossaryTerm={removeCustomGlossaryTerm}
              />
            )}

            {!required && activeTab === "reports" && (
              <ReportsSettingsTab
                reports={reports}
                backtest={backtest}
                memoryQuery={memoryQuery}
                memoryHits={memoryHits}
                onMemoryQueryChange={setMemoryQuery}
                onMemorySearch={(query) => void api.searchMemory(query).then(setMemoryHits)}
              />
            )}

            {!required && activeTab === "about" && <AboutSettingsTab />}
          </div>
        </div>
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
