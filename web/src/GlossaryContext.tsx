import { createContext, useContext, type ReactNode } from "react";
import type { GlossaryTerm } from "./api";

export interface GlossaryContextValue {
  /** 个人模式 + enableGlossary 时为 true */
  enabled: boolean;
  terms: Record<string, GlossaryTerm>;
}

const defaultValue: GlossaryContextValue = {
  enabled: false,
  terms: {},
};

const GlossaryContext = createContext<GlossaryContextValue>(defaultValue);

export function GlossaryProvider({
  enabled,
  terms,
  children,
}: GlossaryContextValue & { children: ReactNode }) {
  return <GlossaryContext.Provider value={{ enabled, terms }}>{children}</GlossaryContext.Provider>;
}

// context hook 与 Provider 同文件是 React 官方模式；HMR 对本 hook 导出不做精确刷新
// eslint-disable-next-line react-refresh/only-export-components
export function useGlossaryContext(): GlossaryContextValue {
  return useContext(GlossaryContext);
}
