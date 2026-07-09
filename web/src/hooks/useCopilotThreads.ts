import { useCallback, useEffect, useRef, useState } from "react";
import type { Message } from "../appTypes";
import {
  autoThreadTitle,
  createThread,
  loadCopilotThreads,
  saveCopilotThreads,
  shouldForkCopilotThread,
  titleFromMessages,
  touchThread,
  type CopilotThread,
  type TopicSymbol,
} from "../copilotThreads";
import { emptyStreamState, type StreamState } from "../streamEvents";

interface UseCopilotThreadsOptions {
  defaultTitle: string;
}

export interface PrepareUserTurnResult {
  threadId: string;
  sessionId: string | undefined;
  forked: boolean;
}

export function useCopilotThreads({ defaultTitle }: UseCopilotThreadsOptions) {
  const [threads, setThreads] = useState<CopilotThread[]>(() => loadCopilotThreads(defaultTitle));
  const [activeId, setActiveId] = useState<string>(() => loadCopilotThreads(defaultTitle)[0]?.id ?? "");
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
      setThreads((prev) => {
        const next = prev.filter((t) => t.id !== id);
        if (next.length === 0) {
          const created = createThread(defaultTitle);
          setActiveId(created.id);
          activeIdRef.current = created.id;
          return [created];
        }
        if (id === activeIdRef.current) {
          setActiveId(next[0].id);
          activeIdRef.current = next[0].id;
          setChatStream(emptyStreamState());
          setInput("");
        }
        return next;
      });
    },
    [defaultTitle],
  );

  const prepareUserTurn = useCallback(
    (query: string, knownSymbols: TopicSymbol[]): PrepareUserTurnResult => {
      const trimmed = query.trim();
      const current =
        threadsRef.current.find((t) => t.id === activeIdRef.current) ?? threadsRef.current[0];
      if (!current) {
        const thread = createThread(autoThreadTitle(trimmed, defaultTitle));
        setThreads([thread]);
        setActiveId(thread.id);
        activeIdRef.current = thread.id;
        const nextMessages: Message[] = [{ role: "user", content: trimmed }];
        persistThread(thread.id, { messages: nextMessages, title: autoThreadTitle(trimmed, defaultTitle) });
        return { threadId: thread.id, sessionId: undefined, forked: false };
      }

      let target = current;
      let forked = false;
      if (shouldForkCopilotThread(current.messages, trimmed, knownSymbols)) {
        const thread = createThread(autoThreadTitle(trimmed, defaultTitle));
        setThreads((prev) => [thread, ...prev].slice(0, 40));
        setActiveId(thread.id);
        activeIdRef.current = thread.id;
        target = thread;
        forked = true;
        setChatStream(emptyStreamState());
      }

      const nextMessages: Message[] = [...target.messages, { role: "user", content: trimmed }];
      const title = titleFromMessages(nextMessages, defaultTitle);
      persistThread(target.id, {
        messages: nextMessages,
        title,
        ...(forked ? { sessionId: undefined } : {}),
      });

      return {
        threadId: target.id,
        sessionId: forked ? undefined : target.sessionId,
        forked,
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
