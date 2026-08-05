import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { applyLocale, loadLocale, saveLocale, type AppLocale } from "./localeSettings";
import { en } from "./locales/en";
import { zh } from "./locales/zh";
import type { Dict } from "./locales/types";

const dictionaries: Record<AppLocale, Dict> = { zh, en };

function resolve(dict: Dict, path: string): string | undefined {
  const parts = path.split(".");
  let cur: string | Dict | undefined = dict;
  for (const part of parts) {
    if (cur == null || typeof cur === "string") return undefined;
    cur = cur[part];
  }
  return typeof cur === "string" ? cur : undefined;
}

export type TParams = Record<string, string | number>;

// 供 processKind.test 等单测直接构造 t；与组件同文件仅影响 HMR 精确度
// eslint-disable-next-line react-refresh/only-export-components
export function createT(locale: AppLocale) {
  const dict = dictionaries[locale];
  return (key: string, params?: TParams): string => {
    let text = resolve(dict, key) ?? resolve(dictionaries.zh, key) ?? key;
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        text = text.split(`{${k}}`).join(String(v));
      }
    }
    return text;
  };
}

interface I18nContextValue {
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
  t: (key: string, params?: TParams) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<AppLocale>(loadLocale);

  const setLocale = useCallback((next: AppLocale) => {
    setLocaleState(next);
    saveLocale(next);
    applyLocale(next);
  }, []);

  const value = useMemo(() => ({ locale, setLocale, t: createT(locale) }), [locale, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

// context hook 与 Provider 同文件是 React 官方模式；HMR 对本 hook 导出不做精确刷新
// eslint-disable-next-line react-refresh/only-export-components
export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}

export type { Dict };
