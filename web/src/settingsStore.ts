/** Unified localStorage settings store factory with in-memory cache. */

export type MigrateFn<T> = (parsed: unknown) => Partial<T> | undefined;
export type ValidateFn<T> = (value: unknown) => value is T;

export interface LocalStorageStoreOptions<T> {
  key: string;
  legacyKeys?: string[];
  defaults: T;
  migrate?: MigrateFn<T>;
  validate?: ValidateFn<T>;
}

export interface LocalStorageStore<T> {
  load: () => T;
  save: (value: T) => void;
  clear: () => void;
  key: string;
}

export function createLocalStorageStore<T extends object>({
  key,
  legacyKeys = [],
  defaults,
  migrate,
  validate,
}: LocalStorageStoreOptions<T>): LocalStorageStore<T> {
  let cached: T | null = null;
  let cachedRaw: string | null = null;

  function load(): T {
    try {
      let raw = localStorage.getItem(key);
      if (!raw) {
        for (const legacy of legacyKeys) {
          raw = localStorage.getItem(legacy);
          if (raw) break;
        }
      }
      if (raw === cachedRaw && cached) return cached;
      cachedRaw = raw;
      if (!raw) {
        cached = { ...defaults };
        return cached;
      }

      const parsed = JSON.parse(raw) as unknown;
      let merged: T;
      if (validate?.(parsed)) {
        merged = { ...defaults, ...(parsed as Partial<T>) };
      } else {
        const migrated = migrate ? migrate(parsed) : (parsed as Partial<T>);
        merged = { ...defaults, ...(migrated ?? {}) };
      }
      cached = merged;
      return cached;
    } catch {
      cached = { ...defaults };
      return cached;
    }
  }

  function save(value: T): void {
    cached = value;
    cachedRaw = JSON.stringify(value);
    localStorage.setItem(key, cachedRaw);
  }

  function clear(): void {
    cached = null;
    cachedRaw = null;
    localStorage.removeItem(key);
  }

  return { load, save, clear, key };
}
