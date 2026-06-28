export type AppTheme = "orange-black" | "wine-red-white" | "paper-white" | "warm-cream";

const STORAGE_KEY = "stockresearch.theme";
const LEGACY_KEYS = ["stockbuddy.theme", "invesbao.theme"];

export const THEME_OPTIONS: { id: AppTheme; label: string; hint: string }[] = [
  { id: "orange-black", label: "橙黑", hint: "Bloomberg 终端 · 橙顶黑底" },
  { id: "wine-red-white", label: "改版酒红", hint: "纯白底 · 酒红顶栏与强调" },
  { id: "paper-white", label: "纸张白", hint: "纯白底 · 中性灰边 · 蓝色强调" },
  { id: "warm-cream", label: "暖米白", hint: "纯白底 · 暖棕顶栏 · 琥珀强调" },
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
    if (
      raw === "wine-red-white" ||
      raw === "dark-red-white" ||
      raw === "paper-white" ||
      raw === "warm-cream"
    ) {
      return raw === "dark-red-white" ? "wine-red-white" : (raw as AppTheme);
    }
    if (raw === "orange-black") return raw;
    if (raw === "slate-modern") return "orange-black";
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

export function isLightTheme(theme: AppTheme): boolean {
  return theme !== "orange-black";
}
