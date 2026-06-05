const STORAGE_KEY = "stockresearch.analysis.settings";

export interface AnalysisUserSettings {
  /** 开启后，股票/市场相关问题在多维分析后追加多空辩论 */
  enableDebate: boolean;
}

const DEFAULTS: AnalysisUserSettings = {
  enableDebate: true,
};

export function loadAnalysisSettings(): AnalysisUserSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    const parsed = JSON.parse(raw) as Partial<AnalysisUserSettings>;
    return {
      enableDebate:
        typeof parsed.enableDebate === "boolean" ? parsed.enableDebate : DEFAULTS.enableDebate,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveAnalysisSettings(settings: AnalysisUserSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function analysisBodyField(): { enable_debate: boolean } {
  return { enable_debate: loadAnalysisSettings().enableDebate };
}
