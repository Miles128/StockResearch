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
