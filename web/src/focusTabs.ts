import type { FocusContext } from "./layoutTypes";

export interface FocusTab {
  id: string;
  context: FocusContext;
}

export function focusTabId(context: FocusContext): string {
  if (context.kind === "stock") return `stock:${context.symbol}`;
  if (context.kind === "index") return `index:${context.symbol}`;
  return `sector:${context.name}`;
}

export function focusTabLabel(context: FocusContext): string {
  if (context.kind === "sector") return context.name;
  return context.name;
}

export function upsertFocusTab(
  tabs: FocusTab[],
  context: FocusContext,
): { tabs: FocusTab[]; activeId: string } {
  const id = focusTabId(context);
  const existing = tabs.some((tab) => tab.id === id);
  if (existing) {
    return {
      tabs: tabs.map((tab) => (tab.id === id ? { id, context } : tab)),
      activeId: id,
    };
  }
  return { tabs: [...tabs, { id, context }], activeId: id };
}

export function removeFocusTab(
  tabs: FocusTab[],
  tabId: string,
): { tabs: FocusTab[]; activeId: string | null } {
  const next = tabs.filter((tab) => tab.id !== tabId);
  if (next.length === 0) return { tabs: [], activeId: null };
  const activeId = next[next.length - 1].id;
  return { tabs: next, activeId };
}

export function activeFocusContext(
  tabs: FocusTab[],
  activeId: string | null,
): FocusContext | null {
  if (!activeId) return null;
  return tabs.find((tab) => tab.id === activeId)?.context ?? null;
}
