export type AppTheme = "orange-black" | "wine-red-white";

const STORAGE_KEY = "stockresearch.theme";
const LEGACY_KEYS = ["stockbuddy.theme", "invesbao.theme"];

export const THEME_OPTIONS: { id: AppTheme; label: string; hint: string }[] = [
  { id: "orange-black", label: "橙黑", hint: "Bloomberg 终端 · 橙顶黑底" },
  { id: "wine-red-white", label: "酒红白", hint: "白底主界面 · 酒红强调" },
];

export function loadTheme(): AppTheme {
  try {
    let raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      for (const key of LEGACY_KEYS) {
        raw = localStorage.getItem(key);
        if (raw) break;
      }
    }
    if (raw === "wine-red-white" || raw === "dark-red-white") return "wine-red-white";
    if (raw === "orange-black") return raw;
  } catch {
    // ignore
  }
  return "orange-black";
}

export function saveTheme(theme: AppTheme): void {
  localStorage.setItem(STORAGE_KEY, theme);
}

export function applyTheme(theme: AppTheme): void {
  document.documentElement.dataset.theme = theme;
}
