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
/** 单线程消息上限：超限丢弃最旧的（保留最近的消息，标题只依赖最新用户消息）。 */
const MAX_MESSAGES_PER_THREAD = 200;
/** 序列化体积安全线（约 localStorage 5MB quota 的一半）：超线后激进裁剪。 */
const MAX_SERIALIZED_BYTES = 2_500_000;
/** 超体积时的保留条数（每线程最近 N 条）。 */
const EMERGENCY_MESSAGES = 30;

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

function trimMessages(messages: Message[]): Message[] {
  return messages.length > MAX_MESSAGES_PER_THREAD
    ? messages.slice(-MAX_MESSAGES_PER_THREAD)
    : messages;
}

export function saveCopilotThreads(threads: CopilotThread[]): void {
  let trimmed = threads
    .slice(0, MAX_THREADS)
    .map((t) => ({ ...t, messages: trimMessages(messagesForStorage(t.messages)) }));
  const serialized = JSON.stringify(trimmed);
  // 超体积时激进裁剪：每线程只保留最近 N 条，避免 localStorage quota 溢出白屏。
  if (serialized.length > MAX_SERIALIZED_BYTES) {
    trimmed = trimmed.map((t) => ({
      ...t,
      messages: trimMessages(t.messages.slice(-EMERGENCY_MESSAGES)),
    }));
  }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch {
    // quota 溢出/隐私模式：静默降级为不持久化（与 usageTracking 容错口径一致）
  }
}

export function touchThread(thread: CopilotThread, patch: Partial<CopilotThread>): CopilotThread {
  return { ...thread, ...patch, updatedAt: Date.now() };
}
