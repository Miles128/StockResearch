import { useCallback, useEffect, useRef, useState } from "react";
import type { Message } from "../appTypes";
import {
  autoThreadTitle,
  createThread,
  loadCopilotThreads,
  saveCopilotThreads,
  touchThread,
  type CopilotThread,
} from "../copilotThreads";
import { emptyStreamState, type StreamState } from "../streamEvents";

interface UseCopilotThreadsOptions {
  defaultTitle: string;
}

export function useCopilotThreads({ defaultTitle }: UseCopilotThreadsOptions) {
  const [threads, setThreads] = useState<CopilotThread[]>(() => loadCopilotThreads(defaultTitle));
  const [activeId, setActiveId] = useState<string>(() => loadCopilotThreads(defaultTitle)[0]?.id ?? "");
  const [chatStream, setChatStream] = useState(emptyStreamState());
  const [input, setInput] = useState("");
  const threadsRef = useRef(threads);
  threadsRef.current = threads;

  const activeThread = threads.find((t) => t.id === activeId) ?? threads[0];
  const messages = activeThread?.messages ?? [];
  const sessionId = activeThread?.sessionId;

  useEffect(() => {
    saveCopilotThreads(threads);
  }, [threads]);

  const persistThread = useCallback((id: string, patch: Partial<CopilotThread>) => {
    setThreads((prev) => prev.map((t) => (t.id === id ? touchThread(t, patch) : t)));
  }, []);

  const switchThread = useCallback(
    (id: string) => {
      if (id === activeId) return;
      setActiveId(id);
      setChatStream(emptyStreamState());
      setInput("");
    },
    [activeId],
  );

  const newThread = useCallback(() => {
    const thread = createThread(defaultTitle);
    setThreads((prev) => [thread, ...prev].slice(0, 40));
    setActiveId(thread.id);
    setChatStream(emptyStreamState());
    setInput("");
  }, [defaultTitle]);

  const renameThread = useCallback((id: string, title: string) => {
    const next = title.trim();
    if (!next) return;
    persistThread(id, { title: next });
  }, [persistThread]);

  const deleteThread = useCallback(
    (id: string) => {
      setThreads((prev) => {
        const next = prev.filter((t) => t.id !== id);
        if (next.length === 0) {
          const created = createThread(defaultTitle);
          setActiveId(created.id);
          return [created];
        }
        if (id === activeId) {
          setActiveId(next[0].id);
          setChatStream(emptyStreamState());
          setInput("");
        }
        return next;
      });
    },
    [activeId, defaultTitle],
  );

  const appendMessages = useCallback(
    (updater: (prev: Message[]) => Message[]) => {
      if (!activeThread) return;
      const nextMessages = updater(activeThread.messages);
      let title = activeThread.title;
      const firstUser = nextMessages.find((m) => m.role === "user");
      if (firstUser?.content.trim()) {
        title = autoThreadTitle(firstUser.content, defaultTitle);
      }
      persistThread(activeThread.id, { messages: nextMessages, title });
    },
    [activeThread, defaultTitle, persistThread],
  );

  const setSessionId = useCallback(
    (nextSessionId: string | undefined) => {
      if (!activeThread) return;
      persistThread(activeThread.id, { sessionId: nextSessionId });
    },
    [activeThread, persistThread],
  );

  const replaceMessages = useCallback(
    (nextMessages: Message[]) => {
      if (!activeThread) return;
      persistThread(activeThread.id, { messages: nextMessages });
    },
    [activeThread, persistThread],
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
    appendMessages,
    replaceMessages,
    setSessionId,
  };
}

export type { CopilotThread, StreamState };
