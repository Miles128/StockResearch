import { createLocalStorageStore } from "./settingsStore";

export interface LayoutSettings {
  copilotWidth: number;
}

const STORAGE_KEY = "stockresearch.layout.settings";

const store = createLocalStorageStore<LayoutSettings>({
  key: STORAGE_KEY,
  defaults: {
    copilotWidth: 380,
  },
});

export function loadLayoutSettings(): LayoutSettings {
  const raw = store.load() as LayoutSettings & { shellLayout?: string; copilotLayout?: string; copilotHeight?: number };
  return { copilotWidth: raw.copilotWidth ?? 380 };
}

export function saveLayoutSettings(value: LayoutSettings): void {
  store.save(value);
}
