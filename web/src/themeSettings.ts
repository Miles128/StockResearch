export type AppTheme = "institutional-light" | "institutional-dark";

const STORAGE_KEY = "stockresearch.theme";
const LEGACY_KEYS = ["stockbuddy.theme", "invesbao.theme"];

const LEGACY_DARK = new Set(["orange-black", "slate-modern", "institutional-dark"]);
const LEGACY_LIGHT = new Set([
  "wine-red-white",
  "dark-red-white",
  "paper-white",
  "warm-cream",
  "institutional-light",
]);

function normalizeLegacyTheme(raw: string): AppTheme | null {
  if (LEGACY_DARK.has(raw)) return "institutional-dark";
  if (LEGACY_LIGHT.has(raw)) {
    return raw === "dark-red-white" ? "institutional-light" : "institutional-light";
  }
  return null;
}

export function loadTheme(): AppTheme {
  try {
    let raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      for (const key of LEGACY_KEYS) {
        raw = localStorage.getItem(key);
        if (raw) break;
      }
    }
    if (raw === "institutional-light" || raw === "institutional-dark") {
      return raw;
    }
    const migrated = raw ? normalizeLegacyTheme(raw) : null;
    if (migrated) return migrated;
  } catch {
    // ignore
  }
  return "institutional-light";
}

export function saveTheme(theme: AppTheme): void {
  localStorage.setItem(STORAGE_KEY, theme);
}

export function applyTheme(theme: AppTheme): void {
  document.documentElement.dataset.theme = theme;
}
