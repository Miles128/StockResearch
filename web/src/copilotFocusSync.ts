import type { ChatResponse } from "./api";
import type { FocusContext } from "./layoutTypes";
import { upsertFocusTab, type FocusTab } from "./focusTabs";

export interface KnownSymbol {
  symbol: string;
  name: string;
}

function researchFromCards(
  cards: ChatResponse["cards"] | undefined,
): KnownSymbol | null {
  if (!cards) return null;
  for (const card of cards) {
    if (card.type !== "research") continue;
    const data = card.data as { symbol?: string; name?: string };
    if (data.symbol && data.name)
      return { symbol: data.symbol, name: data.name };
  }
  return null;
}

function symbolFromCards(
  cards: ChatResponse["cards"] | undefined,
): KnownSymbol | null {
  if (!cards) return null;
  for (const card of cards) {
    const data = card.data as { symbol?: string; name?: string };
    if (data?.symbol && /^\d{6}$/.test(data.symbol)) {
      return { symbol: data.symbol, name: data.name?.trim() || data.symbol };
    }
  }
  return null;
}

function resolveSymbolFromQuery(
  query: string,
  known: KnownSymbol[],
): KnownSymbol | null {
  const codeMatch = query.match(/\b(\d{6})\b/);
  if (codeMatch) {
    const symbol = codeMatch[1];
    const hit = known.find((item) => item.symbol === symbol);
    return hit ?? { symbol, name: symbol };
  }

  const analyzeMatch = query.match(
    /(?:分析|研究|看看|Analyze|Research)\s*[「"'']?([^「」"'(\n，,。!?？\s]{2,20})/i,
  );
  if (analyzeMatch) {
    const token = analyzeMatch[1].trim();
    const byName = known.find(
      (item) =>
        item.name === token ||
        item.name.includes(token) ||
        token.includes(item.name) ||
        item.symbol === token,
    );
    if (byName) return byName;
    if (/^\d{6}$/.test(token)) return { symbol: token, name: token };
  }

  for (const item of known) {
    if (query.includes(item.name) || query.includes(item.symbol)) return item;
  }
  return null;
}

function toStockContext(item: KnownSymbol): FocusContext {
  return { kind: "stock", symbol: item.symbol, name: item.name };
}

/** PRD §4.1 — Copilot intent drives focus tabs after a completed turn. */
export function syncFocusTabsFromChat(
  query: string,
  response: ChatResponse,
  tabs: FocusTab[],
  activeContext: FocusContext | null,
  knownSymbols: KnownSymbol[] = [],
): { tabs: FocusTab[]; activeId: string | null } {
  const compareIntent = /对比|比较|\bvs\b/i.test(query);
  const research =
    researchFromCards(response.cards) ??
    symbolFromCards(response.cards) ??
    resolveSymbolFromQuery(query, knownSymbols);

  if (compareIntent && activeContext?.kind === "stock" && research) {
    let nextTabs = tabs;
    const primary = upsertFocusTab(nextTabs, activeContext);
    nextTabs = primary.tabs;
    const secondary = upsertFocusTab(nextTabs, toStockContext(research));
    return { tabs: secondary.tabs, activeId: secondary.activeId };
  }

  if (research) {
    const next = upsertFocusTab(tabs, toStockContext(research));
    return { tabs: next.tabs, activeId: next.activeId };
  }

  return { tabs, activeId: null };
}

export function buildKnownSymbols(
  holdings: { symbol: string; name: string }[],
  watchlist: { symbol: string; name: string }[],
): KnownSymbol[] {
  const map = new Map<string, KnownSymbol>();
  for (const item of [...holdings, ...watchlist]) {
    if (item.symbol && item.name)
      map.set(item.symbol, { symbol: item.symbol, name: item.name });
  }
  return [...map.values()];
}
