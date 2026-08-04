import { createLocalStorageStore } from "./settingsStore";

export interface LayoutSettings {
  copilotWidth: number;
  listsWidth: number;
}

export const LISTS_WIDTH_MIN = 280;
export const LISTS_WIDTH_MAX = 880;
export const LISTS_WIDTH_DEFAULT = 360;
/** Sidebar width — sector table headers + holdings detail table. */
export const LISTS_DETAIL_WIDTH = 480;
/** Width applied when user clicks expand (») to show all list columns. */
export const LISTS_EXPAND_WIDTH = 720;

const STORAGE_KEY = "stockresearch.layout.settings";

const store = createLocalStorageStore<LayoutSettings>({
  key: STORAGE_KEY,
  defaults: {
    copilotWidth: 380,
    listsWidth: LISTS_WIDTH_DEFAULT,
  },
});

export function loadLayoutSettings(): LayoutSettings {
  const raw = store.load() as LayoutSettings & {
    shellLayout?: string;
    copilotLayout?: string;
    copilotHeight?: number;
  };
  const listsWidth = raw.listsWidth ?? LISTS_WIDTH_DEFAULT;
  return {
    copilotWidth: raw.copilotWidth ?? 380,
    listsWidth: Math.max(LISTS_WIDTH_MIN, Math.min(LISTS_WIDTH_MAX, listsWidth)),
  };
}

export function saveLayoutSettings(value: LayoutSettings): void {
  store.save({
    ...value,
    listsWidth: Math.max(LISTS_WIDTH_MIN, Math.min(LISTS_WIDTH_MAX, value.listsWidth)),
  });
}
