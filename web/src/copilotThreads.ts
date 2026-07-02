import type { Message } from "./appTypes";

export interface CopilotThread {
  id: string;
  title: string;
  sessionId?: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

const STORAGE_KEY = "stockresearch.copilotThreads";
const MAX_THREADS = 40;
const TITLE_MAX = 32;

function newId(): string {
  return `t_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function truncateThreadTitle(text: string, maxLen = TITLE_MAX): string {
  const plain = text.replace(/\s+/g, " ").trim();
  if (!plain) return plain;
  if (plain.length <= maxLen) return plain;
  return `${plain.slice(0, maxLen - 1)}…`;
}

export function autoThreadTitle(firstQuery: string, fallback: string): string {
  const title = truncateThreadTitle(firstQuery);
  return title || fallback;
}

export interface TopicSymbol {
  symbol: string;
  name: string;
}

const MARKET_CUES = ["大盘", "市场", "a股", "指数", "上证", "深证", "创业板", "沪深", "行情", "北向"];
const RISK_CUES = ["风控", "风险", "回撤", "var", "持仓"];
const NEWS_CUES = ["新闻", "快讯", "要闻", "研报"];

function normalizeTopicText(text: string): string {
  return text.toLowerCase().replace(/\s+/g, "");
}

function hasTopicCue(text: string, cues: string[]): boolean {
  const normalized = normalizeTopicText(text);
  return cues.some((cue) => normalized.includes(normalizeTopicText(cue)));
}

function mentionedSymbols(text: string, knownSymbols: TopicSymbol[]): string[] {
  const found: string[] = [];
  for (const item of knownSymbols) {
    if (text.includes(item.symbol)) found.push(item.symbol);
    else if (item.name.length >= 2 && text.includes(item.name)) found.push(item.symbol);
  }
  return [...new Set(found)];
}

function isSameStockFollowUp(
  prevText: string,
  newText: string,
  knownSymbols: TopicSymbol[],
): boolean {
  for (const item of knownSymbols) {
    const prevHit =
      prevText.includes(item.symbol) || (item.name.length >= 2 && prevText.includes(item.name));
    if (!prevHit) continue;
    if (newText.includes(item.symbol) || newText.includes(item.name)) return true;
    for (let i = 0; i < item.name.length - 1; i += 1) {
      const part = item.name.slice(i, i + 2);
      if (part.length === 2 && newText.includes(part)) return true;
    }
  }
  return false;
}

function tokenOverlap(prevText: string, newText: string): number {
  const tokenize = (value: string) =>
    new Set(
      value
        .replace(/[^\u4e00-\u9fffA-Za-z0-9]/g, " ")
        .split(/\s+/)
        .filter((word) => word.length >= 2),
    );
  const prev = tokenize(prevText);
  const next = tokenize(newText);
  if (next.size === 0) return 1;
  let common = 0;
  for (const token of next) {
    if (prev.has(token)) common += 1;
  }
  return common / next.size;
}

/** Fork a new thread when the latest question is clearly unrelated to recent turns. */
export function shouldForkCopilotThread(
  messages: Message[],
  newQuery: string,
  knownSymbols: TopicSymbol[],
): boolean {
  const userMessages = messages.filter((m) => m.role === "user");
  if (userMessages.length === 0) return false;

  const prevText = userMessages
    .slice(-2)
    .map((m) => m.content)
    .join(" ");
  const prevSymbols = mentionedSymbols(prevText, knownSymbols);
  const newSymbols = mentionedSymbols(newQuery, knownSymbols);

  if (prevSymbols.length > 0 && newSymbols.length > 0 && !newSymbols.some((s) => prevSymbols.includes(s))) {
    return true;
  }

  const prevDomain = hasTopicCue(prevText, RISK_CUES)
    ? "risk"
    : hasTopicCue(prevText, MARKET_CUES)
      ? "market"
      : prevSymbols.length > 0
        ? "stock"
        : hasTopicCue(prevText, NEWS_CUES)
          ? "news"
          : "general";
  const newDomain = hasTopicCue(newQuery, RISK_CUES)
    ? "risk"
    : hasTopicCue(newQuery, MARKET_CUES)
      ? "market"
      : newSymbols.length > 0
        ? "stock"
        : hasTopicCue(newQuery, NEWS_CUES)
          ? "news"
          : "general";

  if (prevDomain !== "general" && newDomain !== "general" && prevDomain !== newDomain) {
    return true;
  }

  if (isSameStockFollowUp(prevText, newQuery, knownSymbols)) {
    return false;
  }

  return tokenOverlap(prevText, newQuery) < 0.1 && newQuery.trim().length >= 6;
}

export function titleFromMessages(messages: Message[], fallback: string): string {
  const latestUser = [...messages].reverse().find((m) => m.role === "user" && m.content.trim());
  if (!latestUser) return fallback;
  return autoThreadTitle(latestUser.content, fallback);
}

export function createThread(title: string): CopilotThread {
  const now = Date.now();
  return {
    id: newId(),
    title,
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
}

/** Drop ephemeral stream state before persisting. */
export function messagesForStorage(messages: Message[]): Message[] {
  return messages.map(({ process: _process, ...rest }) => rest);
}

export function loadCopilotThreads(defaultTitle: string): CopilotThread[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [createThread(defaultTitle)];
    const parsed = JSON.parse(raw) as CopilotThread[];
    if (!Array.isArray(parsed) || parsed.length === 0) return [createThread(defaultTitle)];
    return parsed
      .filter((t) => t && typeof t.id === "string")
      .slice(0, MAX_THREADS)
      .map((t) => ({
        ...t,
        messages: Array.isArray(t.messages) ? t.messages : [],
        title: typeof t.title === "string" && t.title.trim() ? t.title : defaultTitle,
      }));
  } catch {
    return [createThread(defaultTitle)];
  }
}

export function saveCopilotThreads(threads: CopilotThread[]): void {
  const trimmed = threads
    .slice(0, MAX_THREADS)
    .map((t) => ({ ...t, messages: messagesForStorage(t.messages) }));
  localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
}

export function touchThread(thread: CopilotThread, patch: Partial<CopilotThread>): CopilotThread {
  return { ...thread, ...patch, updatedAt: Date.now() };
}
