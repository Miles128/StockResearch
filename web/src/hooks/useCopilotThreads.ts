import { useCallback, useEffect, useRef, useState } from "react";
import type { Message } from "../appTypes";
import {
  autoThreadTitle,
  createThread,
  loadCopilotThreads,
  saveCopilotThreads,
  titleFromMessages,
  touchThread,
  type CopilotThread,
} from "../copilotThreads";
import { emptyStreamState, type StreamState } from "../streamEvents";

interface UseCopilotThreadsOptions {
  defaultTitle: string;
}

export interface PrepareUserTurnResult {
  threadId: string;
  sessionId: string | undefined;
}

export function useCopilotThreads({ defaultTitle }: UseCopilotThreadsOptions) {
  // Load once and derive both states from the SAME array. Calling
  // loadCopilotThreads() twice (two lazy initializers) creates two different
  // threads when storage is empty, leaving activeId pointing at a ghost.
  const [initialThreads] = useState(() => loadCopilotThreads(defaultTitle));
  const [threads, setThreads] = useState<CopilotThread[]>(initialThreads);
  const [activeId, setActiveId] = useState<string>(() => initialThreads[0]?.id ?? "");
  const [chatStream, setChatStream] = useState(emptyStreamState());
  const [input, setInput] = useState("");
  const threadsRef = useRef(threads);
  const activeIdRef = useRef(activeId);

  useEffect(() => {
    threadsRef.current = threads;
  }, [threads]);

  useEffect(() => {
    activeIdRef.current = activeId;
  }, [activeId]);

  const activeThread = threads.find((t) => t.id === activeId) ?? threads[0];
  const messages = activeThread?.messages ?? [];
  const sessionId = activeThread?.sessionId;

  useEffect(() => {
    saveCopilotThreads(threads);
  }, [threads]);

  const persistThread = useCallback((id: string, patch: Partial<CopilotThread>) => {
    setThreads((prev) => prev.map((t) => (t.id === id ? touchThread(t, patch) : t)));
  }, []);

  const switchThread = useCallback((id: string) => {
    if (id === activeIdRef.current) return;
    setActiveId(id);
    activeIdRef.current = id;
    setChatStream(emptyStreamState());
    setInput("");
  }, []);

  const newThread = useCallback(() => {
    const thread = createThread(defaultTitle);
    setThreads((prev) => [thread, ...prev].slice(0, 40));
    setActiveId(thread.id);
    activeIdRef.current = thread.id;
    setChatStream(emptyStreamState());
    setInput("");
  }, [defaultTitle]);

  const renameThread = useCallback(
    (id: string, title: string) => {
      const next = title.trim();
      if (!next) return;
      persistThread(id, { title: next });
    },
    [persistThread],
  );

  const deleteThread = useCallback(
    (id: string) => {
      // Compute from the synced ref and apply state changes outside any
      // updater — side effects inside a setThreads updater run twice in
      // StrictMode and are order-dependent.
      const next = threadsRef.current.filter((t) => t.id !== id);
      if (next.length === 0) {
        const created = createThread(defaultTitle);
        setThreads([created]);
        setActiveId(created.id);
        activeIdRef.current = created.id;
        return;
      }
      setThreads(next);
      if (id === activeIdRef.current) {
        setActiveId(next[0].id);
        activeIdRef.current = next[0].id;
        setChatStream(emptyStreamState());
        setInput("");
      }
    },
    [defaultTitle, setChatStream],
  );

  /** Append a user turn to the active thread. Only Plus (`newThread`) starts a new line. */
  const prepareUserTurn = useCallback(
    (query: string): PrepareUserTurnResult => {
      const trimmed = query.trim();
      const current =
        threadsRef.current.find((t) => t.id === activeIdRef.current) ?? threadsRef.current[0];
      if (!current) {
        const title = autoThreadTitle(trimmed, defaultTitle);
        const thread = createThread(title);
        const nextMessages: Message[] = [{ role: "user", content: trimmed }];
        setThreads([{ ...thread, messages: nextMessages, title }]);
        setActiveId(thread.id);
        activeIdRef.current = thread.id;
        return { threadId: thread.id, sessionId: undefined };
      }

      const nextMessages: Message[] = [...current.messages, { role: "user", content: trimmed }];
      const title = titleFromMessages(nextMessages, defaultTitle);
      persistThread(current.id, { messages: nextMessages, title });

      return {
        threadId: current.id,
        sessionId: current.sessionId,
      };
    },
    [defaultTitle, persistThread],
  );

  const appendMessages = useCallback(
    (updater: (prev: Message[]) => Message[], threadId?: string) => {
      const id = threadId ?? activeIdRef.current;
      const thread = threadsRef.current.find((t) => t.id === id);
      if (!thread) return;
      const nextMessages = updater(thread.messages);
      persistThread(id, {
        messages: nextMessages,
        title: titleFromMessages(nextMessages, defaultTitle),
      });
    },
    [defaultTitle, persistThread],
  );

  const setSessionId = useCallback(
    (nextSessionId: string | undefined, threadId?: string) => {
      const id = threadId ?? activeIdRef.current;
      persistThread(id, { sessionId: nextSessionId });
    },
    [persistThread],
  );

  const replaceMessages = useCallback(
    (nextMessages: Message[], threadId?: string) => {
      const id = threadId ?? activeIdRef.current;
      persistThread(id, {
        messages: nextMessages,
        title: titleFromMessages(nextMessages, defaultTitle),
      });
    },
    [defaultTitle, persistThread],
  );

  return {
    threads,
    activeId: activeThread?.id ?? "",
    activeThread,
    messages,
    sessionId,
    input,
    setInput,
    chatStream,
    setChatStream,
    switchThread,
    newThread,
    renameThread,
    deleteThread,
    prepareUserTurn,
    appendMessages,
    replaceMessages,
    setSessionId,
  };
}

export type { CopilotThread, StreamState };
