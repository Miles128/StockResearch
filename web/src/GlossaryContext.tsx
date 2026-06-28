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
  return (
    <GlossaryContext.Provider value={{ enabled, terms }}>{children}</GlossaryContext.Provider>
  );
}

export function useGlossaryContext(): GlossaryContextValue {
  return useContext(GlossaryContext);
}
