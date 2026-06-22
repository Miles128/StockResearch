const STORAGE_KEY = "stockresearch.data.settings";

let _cachedSettings: DataSourceUserSettings | null = null;
let _cachedRaw: string | null = null;

export interface DataSourceUserSettings {
  tushareToken: string;
}

const DEFAULTS: DataSourceUserSettings = {
  tushareToken: "",
};

export function loadDataSourceSettings(): DataSourceUserSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === _cachedRaw && _cachedSettings) return _cachedSettings;
    _cachedRaw = raw;
    if (!raw) {
      _cachedSettings = { ...DEFAULTS };
      return _cachedSettings;
    }
    const parsed = JSON.parse(raw) as Partial<DataSourceUserSettings>;
    _cachedSettings = {
      tushareToken:
        typeof parsed.tushareToken === "string" ? parsed.tushareToken : DEFAULTS.tushareToken,
    };
    return _cachedSettings;
  } catch {
    _cachedSettings = { ...DEFAULTS };
    return _cachedSettings;
  }
}

export function saveDataSourceSettings(settings: DataSourceUserSettings): void {
  _cachedSettings = settings;
  _cachedRaw = JSON.stringify(settings);
  localStorage.setItem(STORAGE_KEY, _cachedRaw);
}

export function dataSourceRequestHeaders(): Record<string, string> {
  const { tushareToken } = loadDataSourceSettings();
  if (!tushareToken.trim()) return {};
  return { "X-Tushare-Token": tushareToken.trim() };
}
