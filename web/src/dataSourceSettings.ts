const STORAGE_KEY = "stockresearch.data.settings";

export interface DataSourceUserSettings {
  tushareToken: string;
}

const DEFAULTS: DataSourceUserSettings = {
  tushareToken: "",
};

export function loadDataSourceSettings(): DataSourceUserSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    const parsed = JSON.parse(raw) as Partial<DataSourceUserSettings>;
    return {
      tushareToken:
        typeof parsed.tushareToken === "string" ? parsed.tushareToken : DEFAULTS.tushareToken,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveDataSourceSettings(settings: DataSourceUserSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function dataSourceRequestHeaders(): Record<string, string> {
  const { tushareToken } = loadDataSourceSettings();
  if (!tushareToken.trim()) return {};
  return { "X-Tushare-Token": tushareToken.trim() };
}
