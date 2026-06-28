/**
 * 双模式设置：个人（advisor）/ 专家（research）
 * 唯一设置源：localStorage + 后端 SQLite（/settings/mode）
 */

import type { Tab } from "./appTypes";
import { loadLocale } from "./localeSettings";
import { createLocalStorageStore } from "./settingsStore";

export type AppMode = "advisor" | "research";
export type ReadingMode = "friendly" | "standard" | "professional";
export type RiskTolerance = "conservative" | "moderate" | "aggressive";
export type HoldingsView = "table" | "cards";

export const BUILTIN_MASTER_IDS = ["buffett", "munger", "burry"] as const;
export type BuiltinMasterId = (typeof BUILTIN_MASTER_IDS)[number];

export interface CustomMaster {
  id: string;
  name: string;
  systemPrompt: string;
}

export interface CustomGlossaryTerm {
  id: string;
  short: string;
  def: string;
  analogy?: string;
  en?: string;
}

export interface ModeSettings {
  mode: AppMode;
  riskTolerance: RiskTolerance;
  monthlyIncome?: number;
  readingMode: ReadingMode;
  enableDebate: boolean;
  enableGlossary: boolean;
  maxSignals: number;
  onboarded: boolean;
  enableMasterCommentary: boolean;
  selectedMasters: string[];
  customMasters: CustomMaster[];
  customGlossary: CustomGlossaryTerm[];
  holdingsView: HoldingsView;
  quoteRefreshMinutes: number;
}

const STORAGE_KEY = "stockresearch.mode.settings";
const LEGACY_ANALYSIS_KEY = "stockresearch.analysis.settings";

function migrateCustomMasters(raw: unknown): CustomMaster[] {
  if (!Array.isArray(raw)) return [];
  const out: CustomMaster[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const row = item as Partial<CustomMaster & { system_prompt?: string }>;
    const id = typeof row.id === "string" ? row.id.trim().toLowerCase() : "";
    const name = typeof row.name === "string" ? row.name.trim() : "";
    const systemPrompt =
      typeof row.systemPrompt === "string"
        ? row.systemPrompt
        : typeof row.system_prompt === "string"
          ? row.system_prompt
          : "";
    if (id && name && systemPrompt.length >= 10) {
      out.push({ id, name, systemPrompt });
    }
  }
  return out;
}

function migrateCustomGlossary(raw: unknown): CustomGlossaryTerm[] {
  if (!Array.isArray(raw)) return [];
  const out: CustomGlossaryTerm[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const row = item as Partial<CustomGlossaryTerm & { def?: string }>;
    const short = typeof row.short === "string" ? row.short.trim() : "";
    const def = typeof row.def === "string" ? row.def.trim() : "";
    const id = typeof row.id === "string" && row.id.trim() ? row.id.trim() : short;
    if (!id || !short || def.length < 2) continue;
    out.push({
      id,
      short,
      def,
      analogy: typeof row.analogy === "string" ? row.analogy.trim() : undefined,
      en: typeof row.en === "string" ? row.en.trim() : undefined,
    });
  }
  return out;
}

function migrateFromLegacyAnalysis(): Partial<ModeSettings> {
  try {
    const raw = localStorage.getItem(LEGACY_ANALYSIS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Partial<{
      enableDebate: boolean;
      readingMode: ReadingMode;
      enableMasterCommentary: boolean;
      outputTone?: string;
    }>;
    const partial: Partial<ModeSettings> = {};
    if (typeof parsed.enableDebate === "boolean") partial.enableDebate = parsed.enableDebate;
    if (typeof parsed.enableMasterCommentary === "boolean") {
      partial.enableMasterCommentary = parsed.enableMasterCommentary;
    }
    if (parsed.readingMode === "professional" || parsed.readingMode === "friendly" || parsed.readingMode === "standard") {
      partial.readingMode = parsed.readingMode;
    } else if (parsed.outputTone === "professional") {
      partial.readingMode = "professional";
    } else if (parsed.outputTone === "standard") {
      partial.readingMode = "standard";
    } else if (parsed.outputTone === "friendly") {
      partial.readingMode = "friendly";
    }
    return partial;
  } catch {
    return {};
  }
}

function migrateModeSettings(parsed: unknown): Partial<ModeSettings> {
  const legacy = migrateFromLegacyAnalysis();
  if (!parsed || typeof parsed !== "object") return legacy;
  const partial = parsed as Partial<ModeSettings> & {
    selected_masters?: string[];
    custom_masters?: unknown;
    custom_glossary?: unknown;
    enable_master_commentary?: boolean;
  };
  const mode: AppMode = partial.mode === "research" ? "research" : "advisor";
  const preset = mode === "advisor" ? ADVISOR_PRESET : RESEARCH_PRESET;
  const selectedMasters = Array.isArray(partial.selectedMasters)
    ? partial.selectedMasters.filter((id) => typeof id === "string")
    : Array.isArray(partial.selected_masters)
      ? partial.selected_masters.filter((id) => typeof id === "string")
      : preset.selectedMasters;

  return {
    ...legacy,
    mode,
    riskTolerance:
      partial.riskTolerance === "conservative" ||
      partial.riskTolerance === "moderate" ||
      partial.riskTolerance === "aggressive"
        ? partial.riskTolerance
        : preset.riskTolerance,
    monthlyIncome:
      typeof partial.monthlyIncome === "number" && partial.monthlyIncome > 0
        ? partial.monthlyIncome
        : undefined,
    readingMode:
      partial.readingMode === "professional" ||
      partial.readingMode === "friendly" ||
      partial.readingMode === "standard"
        ? partial.readingMode
        : legacy.readingMode ?? preset.readingMode,
    enableDebate:
      typeof partial.enableDebate === "boolean"
        ? partial.enableDebate
        : legacy.enableDebate ?? preset.enableDebate,
    enableGlossary:
      typeof partial.enableGlossary === "boolean" ? partial.enableGlossary : preset.enableGlossary,
    maxSignals: typeof partial.maxSignals === "number" ? partial.maxSignals : preset.maxSignals,
    onboarded: typeof partial.onboarded === "boolean" ? partial.onboarded : false,
    enableMasterCommentary:
      typeof partial.enableMasterCommentary === "boolean"
        ? partial.enableMasterCommentary
        : typeof partial.enable_master_commentary === "boolean"
          ? partial.enable_master_commentary
          : legacy.enableMasterCommentary ?? preset.enableMasterCommentary,
    selectedMasters: selectedMasters.length > 0 ? selectedMasters : [...BUILTIN_MASTER_IDS],
    customMasters: migrateCustomMasters(partial.customMasters ?? partial.custom_masters),
    customGlossary: migrateCustomGlossary(partial.customGlossary ?? partial.custom_glossary),
    holdingsView:
      partial.holdingsView === "cards" || partial.holdingsView === "table"
        ? partial.holdingsView
        : "table",
    quoteRefreshMinutes:
      typeof partial.quoteRefreshMinutes === "number"
        ? Math.min(120, Math.max(1, partial.quoteRefreshMinutes))
        : typeof (partial as { quote_refresh_minutes?: number }).quote_refresh_minutes === "number"
          ? Math.min(
              120,
              Math.max(1, (partial as { quote_refresh_minutes: number }).quote_refresh_minutes),
            )
          : preset.quoteRefreshMinutes,
  };
}

export interface CustomMasterApiPayload {
  id: string;
  name: string;
  system_prompt: string;
}

export interface CustomGlossaryApiPayload {
  id: string;
  short: string;
  def: string;
  analogy?: string;
  en?: string;
}

export interface ModeSettingsApiPayload {
  mode: AppMode;
  risk_tolerance: RiskTolerance;
  monthly_income?: number | null;
  reading_mode: ReadingMode;
  enable_debate: boolean;
  enable_glossary: boolean;
  max_signals: number;
  onboarded: boolean;
  enable_master_commentary: boolean;
  selected_masters: string[];
  custom_masters: CustomMasterApiPayload[];
  custom_glossary: CustomGlossaryApiPayload[];
  quote_refresh_minutes: number;
}

export const ADVISOR_PRESET: Omit<ModeSettings, "onboarded"> = {
  mode: "advisor",
  riskTolerance: "moderate",
  monthlyIncome: undefined,
  readingMode: "friendly",
  enableDebate: false,
  enableGlossary: true,
  maxSignals: 5,
  enableMasterCommentary: false,
  selectedMasters: [...BUILTIN_MASTER_IDS],
  customMasters: [],
  customGlossary: [],
  holdingsView: "table",
  quoteRefreshMinutes: 10,
};

export const RESEARCH_PRESET: Omit<ModeSettings, "onboarded"> = {
  mode: "research",
  riskTolerance: "moderate",
  monthlyIncome: undefined,
  readingMode: "professional",
  enableDebate: true,
  enableGlossary: false,
  maxSignals: 20,
  enableMasterCommentary: false,
  selectedMasters: [...BUILTIN_MASTER_IDS],
  customMasters: [],
  customGlossary: [],
  holdingsView: "table",
  quoteRefreshMinutes: 10,
};

export const DEFAULT_MODE_SETTINGS: ModeSettings = {
  ...ADVISOR_PRESET,
  onboarded: false,
};

const modeSettingsStore = createLocalStorageStore<ModeSettings>({
  key: STORAGE_KEY,
  defaults: DEFAULT_MODE_SETTINGS,
  migrate: migrateModeSettings,
});

export function presetForMode(
  mode: AppMode,
  current: ModeSettings,
): Pick<
  ModeSettings,
  "mode" | "readingMode" | "enableDebate" | "enableGlossary" | "maxSignals"
> {
  const preset = mode === "advisor" ? ADVISOR_PRESET : RESEARCH_PRESET;
  return {
    mode,
    readingMode: preset.readingMode,
    enableDebate: preset.enableDebate,
    enableGlossary: preset.enableGlossary,
    maxSignals: preset.maxSignals,
  };
}

export function isPristinePreset(settings: ModeSettings): boolean {
  const preset = settings.mode === "advisor" ? ADVISOR_PRESET : RESEARCH_PRESET;
  return (
    settings.readingMode === preset.readingMode &&
    settings.enableDebate === preset.enableDebate &&
    settings.enableGlossary === preset.enableGlossary &&
    settings.maxSignals === preset.maxSignals
  );
}

export function loadModeSettings(): ModeSettings {
  return modeSettingsStore.load();
}

export function saveModeSettings(settings: ModeSettings): void {
  modeSettingsStore.save(settings);
}

export function modeSettingsToApiPayload(settings: ModeSettings): ModeSettingsApiPayload {
  return {
    mode: settings.mode,
    risk_tolerance: settings.riskTolerance,
    monthly_income: settings.monthlyIncome ?? null,
    reading_mode: settings.readingMode,
    enable_debate: settings.enableDebate,
    enable_glossary: settings.enableGlossary,
    max_signals: settings.maxSignals,
    onboarded: settings.onboarded,
    enable_master_commentary: settings.enableMasterCommentary,
    selected_masters: settings.selectedMasters,
    custom_masters: settings.customMasters.map((m) => ({
      id: m.id,
      name: m.name,
      system_prompt: m.systemPrompt,
    })),
    custom_glossary: settings.customGlossary.map((term) => ({
      id: term.id,
      short: term.short,
      def: term.def,
      analogy: term.analogy ?? "",
      en: term.en ?? "",
    })),
    quote_refresh_minutes: settings.quoteRefreshMinutes,
  };
}

export function modeSettingsFromApiPayload(payload: Partial<ModeSettingsApiPayload>): ModeSettings {
  const mode: AppMode = payload.mode === "research" ? "research" : "advisor";
  const preset = mode === "advisor" ? ADVISOR_PRESET : RESEARCH_PRESET;
  return {
    mode,
    riskTolerance:
      payload.risk_tolerance === "conservative" ||
      payload.risk_tolerance === "moderate" ||
      payload.risk_tolerance === "aggressive"
        ? payload.risk_tolerance
        : preset.riskTolerance,
    monthlyIncome:
      typeof payload.monthly_income === "number" && payload.monthly_income > 0
        ? payload.monthly_income
        : undefined,
    readingMode:
      payload.reading_mode === "professional" ||
      payload.reading_mode === "friendly" ||
      payload.reading_mode === "standard"
        ? payload.reading_mode
        : preset.readingMode,
    enableDebate:
      typeof payload.enable_debate === "boolean" ? payload.enable_debate : preset.enableDebate,
    enableGlossary:
      typeof payload.enable_glossary === "boolean" ? payload.enable_glossary : preset.enableGlossary,
    maxSignals:
      typeof payload.max_signals === "number" ? payload.max_signals : preset.maxSignals,
    onboarded: typeof payload.onboarded === "boolean" ? payload.onboarded : false,
    enableMasterCommentary:
      typeof payload.enable_master_commentary === "boolean"
        ? payload.enable_master_commentary
        : preset.enableMasterCommentary,
    selectedMasters:
      Array.isArray(payload.selected_masters) && payload.selected_masters.length > 0
        ? payload.selected_masters
        : [...BUILTIN_MASTER_IDS],
    customMasters: migrateCustomMasters(payload.custom_masters),
    customGlossary: migrateCustomGlossary(payload.custom_glossary),
    holdingsView: "table",
    quoteRefreshMinutes:
      typeof payload.quote_refresh_minutes === "number"
        ? Math.min(120, Math.max(1, payload.quote_refresh_minutes))
        : preset.quoteRefreshMinutes,
  };
}

export function switchMode(settings: ModeSettings, mode: AppMode): ModeSettings {
  const preset = presetForMode(mode, settings);
  return {
    ...settings,
    ...preset,
  };
}

export function isCashFlowEnabled(settings: ModeSettings): boolean {
  return settings.mode === "advisor" && typeof settings.monthlyIncome === "number" && settings.monthlyIncome > 0;
}

export function isRiskToleranceEnabled(settings: ModeSettings): boolean {
  return settings.mode === "advisor";
}

export function lossToIncomeRatio(lossAmount: number, settings: ModeSettings): string | null {
  if (!isCashFlowEnabled(settings) || !settings.monthlyIncome) return null;
  const ratio = (lossAmount / settings.monthlyIncome) * 100;
  return `${ratio.toFixed(1)}%`;
}

export function defaultTabForMode(_mode: AppMode): Tab {
  return "portfolio";
}

export const READING_MODE_I18N_KEYS: Record<
  ReadingMode,
  { label: string; hint: string; short: string }
> = {
  friendly: {
    label: "settings.modeFriendly",
    hint: "settings.modeFriendlyHint",
    short: "settings.modeFriendlyShort",
  },
  standard: {
    label: "settings.modeStandard",
    hint: "settings.modeStandardHint",
    short: "settings.modeStandardShort",
  },
  professional: {
    label: "settings.modeProfessional",
    hint: "settings.modeProfessionalHint",
    short: "settings.modeProfessionalShort",
  },
};

export function chatBodyField(): {
  enable_debate: boolean;
  enable_master_commentary: boolean;
  enable_glossary: boolean;
  reading_mode: ReadingMode;
  output_locale: "zh" | "en";
} {
  const settings = loadModeSettings();
  return {
    enable_debate: settings.enableDebate,
    enable_master_commentary: settings.enableMasterCommentary,
    enable_glossary: settings.enableGlossary,
    reading_mode: settings.readingMode,
    output_locale: loadLocale(),
  };
}
