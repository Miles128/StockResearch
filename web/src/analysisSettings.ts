import { loadLocale } from "./localeSettings";
import { loadModeSettings } from "./modeSettings";

const STORAGE_KEY = "stockresearch.analysis.settings";

/** 阅读模式：专业（术语直出+弹窗） vs 友善（人话+类比） */
export type ReadingMode = "professional" | "friendly";

export interface AnalysisUserSettings {
  /** 开启后，股票/市场相关问题在多维分析后追加多空辩论 */
  enableDebate: boolean;
  /** 阅读模式，默认友善 */
  readingMode: ReadingMode;
  /** 开启后，股票/市场/风控分析结果追加投资大师点评 */
  enableMasterCommentary: boolean;
}

const DEFAULTS: AnalysisUserSettings = {
  enableDebate: true,
  readingMode: "friendly",
  enableMasterCommentary: false,
};

export function loadAnalysisSettings(): AnalysisUserSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    const parsed = JSON.parse(raw) as Partial<AnalysisUserSettings> & { outputTone?: string };
    const mode = parsed.readingMode;
    // Backward compat: if old outputTone exists, map to readingMode
    const tone = parsed.outputTone;
    let readingMode: ReadingMode = DEFAULTS.readingMode;
    if (mode === "professional" || mode === "friendly") {
      readingMode = mode;
    } else if (tone === "professional" || tone === "standard") {
      readingMode = "professional";
    } else if (tone === "friendly") {
      readingMode = "friendly";
    }
    return {
      enableDebate:
        typeof parsed.enableDebate === "boolean" ? parsed.enableDebate : DEFAULTS.enableDebate,
      readingMode,
      enableMasterCommentary:
        typeof parsed.enableMasterCommentary === "boolean"
          ? parsed.enableMasterCommentary
          : DEFAULTS.enableMasterCommentary,
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
  enable_master_commentary: boolean;
  enable_glossary: boolean;
  reading_mode: ReadingMode;
  output_locale: "zh" | "en";
} {
  // 优先读 modeSettings（双模式架构），回退到 analysisSettings
  const mode = loadModeSettings();
  const settings = loadAnalysisSettings();
  return {
    enable_debate: mode.enableDebate,
    enable_master_commentary: settings.enableMasterCommentary,
    enable_glossary: mode.enableGlossary,
    reading_mode: mode.readingMode,
    output_locale: loadLocale(),
  };
}
