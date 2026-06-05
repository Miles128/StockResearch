export type AppLocale = "zh" | "en";

const STORAGE_KEY = "stockresearch.locale";

export function loadLocale(): AppLocale {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === "en" || raw === "zh") return raw;
  } catch {
    // ignore
  }
  return "zh";
}

export function saveLocale(locale: AppLocale): void {
  localStorage.setItem(STORAGE_KEY, locale);
}

export function applyLocale(locale: AppLocale): void {
  document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
}
