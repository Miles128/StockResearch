/**
 * 双模式设置：个人投顾（advisor）/ 专业投研（research）
 * 核心差异：
 * 1. 投顾模式考虑个人现金流和风险承受能力，投研模式不考虑
 * 2. 投顾模式用大白话，投研模式术语直出
 *
 * 模式是预设包，模式内单项可微调（Settings）。
 * 持久化到 localStorage，下次打开记住选择。
 */

import type { Tab } from "./appTypes";
import type { ReadingMode } from "./analysisSettings";

export type AppMode = "advisor" | "research";

/** 风险承受能力分级（投顾模式专属） */
export type RiskTolerance = "conservative" | "moderate" | "aggressive";

export interface ModeSettings {
  /** 当前模式 */
  mode: AppMode;
  /** 风险承受能力分级（投顾模式必填，投研模式不启用） */
  riskTolerance: RiskTolerance;
  /** 月收入（可选，投顾模式用于把亏损换算成"相当于月收入 X%"） */
  monthlyIncome?: number;
  /** 写作风格：投顾默认 friendly（大白话），投研默认 professional（术语） */
  readingMode: ReadingMode;
  /** 多空辩论：投顾默认关，投研默认开 */
  enableDebate: boolean;
  /** 术语弹窗：投顾默认开，投研默认关 */
  enableGlossary: boolean;
  /** 首屏信号数：投顾默认 5，投研默认 20 */
  maxSignals: number;
  /** 是否已完成首次引导 */
  onboarded: boolean;
}

const STORAGE_KEY = "stockresearch.mode.settings";

/** 投顾模式默认预设 */
export const ADVISOR_PRESET: Omit<ModeSettings, "onboarded"> = {
  mode: "advisor",
  riskTolerance: "moderate",
  monthlyIncome: undefined,
  readingMode: "friendly",
  enableDebate: false,
  enableGlossary: true,
  maxSignals: 5,
};

/** 投研模式默认预设 */
export const RESEARCH_PRESET: Omit<ModeSettings, "onboarded"> = {
  mode: "research",
  riskTolerance: "moderate", // 投研模式不启用，但保留默认值
  monthlyIncome: undefined,
  readingMode: "professional",
  enableDebate: true,
  enableGlossary: false,
  maxSignals: 20,
};

/** 默认设置：投顾模式（PRD §1.3 主用户 A 默认） */
export const DEFAULT_MODE_SETTINGS: ModeSettings = {
  ...ADVISOR_PRESET,
  onboarded: false,
};

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
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_MODE_SETTINGS };
    const parsed = JSON.parse(raw) as Partial<ModeSettings>;
    // 合并默认值，确保新字段有兜底
    const mode: AppMode = parsed.mode === "research" ? "research" : "advisor";
    const preset = mode === "advisor" ? ADVISOR_PRESET : RESEARCH_PRESET;
    return {
      mode,
      riskTolerance:
        parsed.riskTolerance === "conservative" ||
        parsed.riskTolerance === "moderate" ||
        parsed.riskTolerance === "aggressive"
          ? parsed.riskTolerance
          : preset.riskTolerance,
      monthlyIncome:
        typeof parsed.monthlyIncome === "number" && parsed.monthlyIncome > 0
          ? parsed.monthlyIncome
          : undefined,
      readingMode: parsed.readingMode === "professional" || parsed.readingMode === "friendly"
        ? parsed.readingMode
        : preset.readingMode,
      enableDebate: typeof parsed.enableDebate === "boolean" ? parsed.enableDebate : preset.enableDebate,
      enableGlossary: typeof parsed.enableGlossary === "boolean" ? parsed.enableGlossary : preset.enableGlossary,
      maxSignals: typeof parsed.maxSignals === "number" ? parsed.maxSignals : preset.maxSignals,
      onboarded: typeof parsed.onboarded === "boolean" ? parsed.onboarded : false,
    };
  } catch {
    return { ...DEFAULT_MODE_SETTINGS };
  }
}

export function saveModeSettings(settings: ModeSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
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
