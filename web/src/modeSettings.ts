/**
 * 双模式设置：个人（advisor）/ 专家（research）
 * 核心差异：
 * 1. 个人模式考虑个人现金流和风险承受能力，专家模式不考虑
 * 2. 个人模式用大白话，专家模式术语直出
 *
 * 模式是预设包，模式内单项可微调（Settings）。
 * 持久化到 localStorage + 后端 SQLite；localStorage 作为启动缓存。
 */

import type { Tab } from "./appTypes";
import type { ReadingMode } from "./analysisSettings";
import { createLocalStorageStore } from "./settingsStore";

export type AppMode = "advisor" | "research";

/** 风险承受能力分级（投顾模式专属） */
export type RiskTolerance = "conservative" | "moderate" | "aggressive";

export interface ModeSettings {
  /** 当前模式 */
  mode: AppMode;
  /** 风险承受能力分级（个人模式专属） */
  riskTolerance: RiskTolerance;
  /** 月收入（可选，个人模式用于把亏损换算成"相当于月收入 X%"） */
  monthlyIncome?: number;
  /** 写作风格：个人默认 friendly（大白话），专家默认 professional（术语） */
  readingMode: ReadingMode;
  /** 多空辩论：个人默认关，专家默认开 */
  enableDebate: boolean;
  /** 术语弹窗：个人默认开，专家默认关 */
  enableGlossary: boolean;
  /** 首屏信号数：个人默认 5，专家默认 20 */
  maxSignals: number;
  /** 是否已完成首次引导 */
  onboarded: boolean;
}

const STORAGE_KEY = "stockresearch.mode.settings";

function migrateModeSettings(parsed: unknown): Partial<ModeSettings> {
  if (!parsed || typeof parsed !== "object") return {};
  const partial = parsed as Partial<ModeSettings>;
  const mode: AppMode = partial.mode === "research" ? "research" : "advisor";
  const preset = mode === "advisor" ? ADVISOR_PRESET : RESEARCH_PRESET;
  return {
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
      partial.readingMode === "professional" || partial.readingMode === "friendly"
        ? partial.readingMode
        : preset.readingMode,
    enableDebate: typeof partial.enableDebate === "boolean" ? partial.enableDebate : preset.enableDebate,
    enableGlossary: typeof partial.enableGlossary === "boolean" ? partial.enableGlossary : preset.enableGlossary,
    maxSignals: typeof partial.maxSignals === "number" ? partial.maxSignals : preset.maxSignals,
    onboarded: typeof partial.onboarded === "boolean" ? partial.onboarded : false,
  };
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
}

/** 个人模式默认预设 */
export const ADVISOR_PRESET: Omit<ModeSettings, "onboarded"> = {
  mode: "advisor",
  riskTolerance: "moderate",
  monthlyIncome: undefined,
  readingMode: "friendly",
  enableDebate: false,
  enableGlossary: true,
  maxSignals: 5,
};

/** 专家模式默认预设 */
export const RESEARCH_PRESET: Omit<ModeSettings, "onboarded"> = {
  mode: "research",
  riskTolerance: "moderate", // 专家模式不启用，但保留默认值
  monthlyIncome: undefined,
  readingMode: "professional",
  enableDebate: true,
  enableGlossary: false,
  maxSignals: 20,
};

/** 默认设置：个人模式（PRD §1.3 主用户 A 默认） */
export const DEFAULT_MODE_SETTINGS: ModeSettings = {
  ...ADVISOR_PRESET,
  onboarded: false,
};

const modeSettingsStore = createLocalStorageStore<ModeSettings>({
  key: STORAGE_KEY,
  defaults: DEFAULT_MODE_SETTINGS,
  migrate: migrateModeSettings,
});

/** 按模式获取预设（保留用户已填的 riskTolerance/monthlyIncome） */
export function presetForMode(
  mode: AppMode,
  current: ModeSettings,
): Pick<ModeSettings, "mode" | "readingMode" | "enableDebate" | "enableGlossary" | "maxSignals"> {
  const preset = mode === "advisor" ? ADVISOR_PRESET : RESEARCH_PRESET;
  return {
    mode,
    readingMode: preset.readingMode,
    enableDebate: preset.enableDebate,
    enableGlossary: preset.enableGlossary,
    maxSignals: preset.maxSignals,
  };
}

/** 判断当前设置是否与模式预设一致（用于 Settings 显示"已自定义"） */
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
      payload.reading_mode === "professional" || payload.reading_mode === "friendly"
        ? payload.reading_mode
        : preset.readingMode,
    enableDebate:
      typeof payload.enable_debate === "boolean" ? payload.enable_debate : preset.enableDebate,
    enableGlossary:
      typeof payload.enable_glossary === "boolean" ? payload.enable_glossary : preset.enableGlossary,
    maxSignals:
      typeof payload.max_signals === "number" ? payload.max_signals : preset.maxSignals,
    onboarded: typeof payload.onboarded === "boolean" ? payload.onboarded : false,
  };
}

/** 切换模式：应用新模式的预设，保留 riskTolerance/monthlyIncome（投顾专属字段） */
export function switchMode(settings: ModeSettings, mode: AppMode): ModeSettings {
  const preset = presetForMode(mode, settings);
  return {
    ...settings,
    ...preset,
  };
}

/** 投顾模式是否启用现金流上下文（有月收入才启用换算） */
export function isCashFlowEnabled(settings: ModeSettings): boolean {
  return settings.mode === "advisor" && typeof settings.monthlyIncome === "number" && settings.monthlyIncome > 0;
}

/** 投顾模式是否启用风险承受能力（投研模式不启用） */
export function isRiskToleranceEnabled(settings: ModeSettings): boolean {
  return settings.mode === "advisor";
}

/** 把亏损金额换算成"相当于月收入 X%"（投顾模式专属） */
export function lossToIncomeRatio(lossAmount: number, settings: ModeSettings): string | null {
  if (!isCashFlowEnabled(settings) || !settings.monthlyIncome) return null;
  const ratio = (lossAmount / settings.monthlyIncome) * 100;
  return `${ratio.toFixed(1)}%`;
}

/** Both modes open on the holdings canvas; mode changes presentation depth. */
export function defaultTabForMode(_mode: AppMode): Tab {
  return "portfolio";
}
