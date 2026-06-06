import { loadLocale } from "./localeSettings";

const STORAGE_KEY = "stockresearch.analysis.settings";

/** 分析输出文风：非常专业 / 普通 / 平易近人 */
export type OutputTone = "professional" | "standard" | "friendly";

export interface AnalysisUserSettings {
  /** 开启后，股票/市场相关问题在多维分析后追加多空辩论 */
  enableDebate: boolean;
  /** 分析内容的语言专业性，默认非常专业 */
  outputTone: OutputTone;
}

const DEFAULTS: AnalysisUserSettings = {
  enableDebate: true,
  outputTone: "professional",
};

export function loadAnalysisSettings(): AnalysisUserSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    const parsed = JSON.parse(raw) as Partial<AnalysisUserSettings>;
    const tone = parsed.outputTone;
    return {
      enableDebate:
        typeof parsed.enableDebate === "boolean" ? parsed.enableDebate : DEFAULTS.enableDebate,
      outputTone:
        tone === "professional" || tone === "standard" || tone === "friendly"
          ? tone
          : DEFAULTS.outputTone,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveAnalysisSettings(settings: AnalysisUserSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function analysisBodyField(): {
  enable_debate: boolean;
  output_tone: OutputTone;
  output_locale: "zh" | "en";
} {
  const settings = loadAnalysisSettings();
  return {
    enable_debate: settings.enableDebate,
    output_tone: settings.outputTone,
    output_locale: loadLocale(),
  };
}
