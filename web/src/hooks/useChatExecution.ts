import { useCallback, useRef, useState } from "react";
import { api, type AgentStreamEvent, type ChatStreamOptions, type HoldingEnriched } from "../api";
import type { CopilotContext, Message } from "../appTypes";
import type { FocusContext } from "../layoutTypes";
import { copilotContextToPayload } from "../chatContext";
import { syncFocusTabsFromChat, type KnownSymbol } from "../copilotFocusSync";
import { stripDisclaimer } from "../disclaimerText";
import {
  applyStreamEvent,
  emptyStreamState,
  finalizeStreamState,
  hasProcessContent,
  type StreamState,
} from "../streamEvents";
import { normalizeStreamEvent } from "../streamI18n";
import type { FocusTab } from "../focusTabs";
import { formatBriefingMarkdown, localizeBriefing } from "../uiLabels";
import { recordLlmUsage } from "../llmUsageStats";

function formatChatRequestError(err: unknown, t: (key: string) => string): string {
  const message = String(err);
  if (err instanceof TypeError && message.includes("Failed to fetch")) {
    return `${t("health.unreachableTitle")}。${t("health.unreachableHint")}`;
  }
  return message;
}

export interface UseChatExecutionOptions {
  t: (key: string, params?: Record<string, string | number>) => string;
  locale: string;
  sessionId: string | undefined;
  pageContext: CopilotContext | null;
  focusContext: FocusContext | null;
  knownSymbols: KnownSymbol[];
  appendMessages: (updater: (messages: Message[]) => Message[], threadId?: string) => void;
  prepareUserTurn: (query: string) => {
    threadId: string;
    sessionId: string | undefined;
  };
  input: string;
  setInput: (value: string) => void;
  setChatStream: (updater: (prev: StreamState) => StreamState) => void;
  setFocusTabs: (updater: (tabs: FocusTab[]) => FocusTab[]) => void;
  setActiveFocusTabId: (id: string | null) => void;
  setCenterTab: (tab: "focus" | "market" | "risk" | "news") => void;
  setCopilotOpen: (open: boolean) => void;
  setPageContext: (ctx: CopilotContext | null) => void;
  openFocus: (context: FocusContext) => void;
  setSessionId: (id: string | undefined, threadId?: string) => void;
}

export interface ChatExecutionState {
  chatLoading: boolean;
  statusMsg: string;
  executeChat: (
    query: string,
    options?: ChatStreamOptions,
    contextOverride?: CopilotContext | null,
  ) => Promise<void>;
  startChatQuery: (
    query: string,
    opts?: { switchTab?: boolean; context?: CopilotContext | null },
  ) => void;
  sendChat: () => void;
  analyzeHolding: (h: HoldingEnriched) => void;
  runBriefingInCopilot: (
    userLabel: string,
    kind: "premarket" | "intraday" | "postmarket",
  ) => Promise<void>;
  confirmChatStock: (originalMessage: string, symbol: string, name: string) => void;
  openCopilotQuery: (query: string) => void;
}

export function useChatExecution(options: UseChatExecutionOptions): ChatExecutionState {
  const {
    t,
    locale,
    sessionId,
    setSessionId,
    pageContext,
    focusContext,
    knownSymbols,
    appendMessages,
    prepareUserTurn,
    input,
    setInput,
    setChatStream,
    setFocusTabs,
    setActiveFocusTabId,
    setCenterTab,
    setCopilotOpen,
    setPageContext,
    openFocus,
  } = options;

  const [chatLoading, setChatLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  const executeChat = useCallback(
    async (
      query: string,
      chatOptions?: ChatStreamOptions,
      contextOverride?: CopilotContext | null,
      turn?: { threadId: string; sessionId: string | undefined },
    ) => {
      const threadId = turn?.threadId;
      const activeSessionId = turn?.sessionId ?? sessionId;
      // Abort any in-flight stream before starting a new one.
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setChatLoading(true);
      setStatusMsg(t("chat.connecting"));
      setChatStream(() => emptyStreamState());
      let processSnapshot = emptyStreamState();
      const activeContext = contextOverride === undefined ? pageContext : contextOverride;
      const resolvedOptions: ChatStreamOptions = {
        ...chatOptions,
        userContext: activeContext ? copilotContextToPayload(activeContext) : null,
      };
      try {
        const resp = await api.chatStream(
          query,
          activeSessionId,
          (event: AgentStreamEvent) => {
            if (event.type === "stock_choice") return;
            const normalized = normalizeStreamEvent(event, t);
            setChatStream((prev) => {
              const next = applyStreamEvent(prev, normalized, t);
              processSnapshot = next;
              return next;
            });
            if (normalized.type === "status" && normalized.message) {
              setStatusMsg(normalized.message);
            }
          },
          resolvedOptions,
          controller.signal,
        );
        // Superseded by a newer turn — drop the stale result.
        if (controller.signal.aborted) return;
        if (!resp) {
          // SSE ended without a done event (timeout/disconnect); fall back to
          // the sync endpoint instead of silently dropping the user's query.
          throw new Error("chat stream ended without a result");
        }
        {
          setSessionId(resp.session_id, threadId);
          recordLlmUsage(resp.llm_usage);
          processSnapshot = finalizeStreamState(
            { ...processSnapshot, streamStatus: t("chat.analysisDone") },
            t("chat.analysisDone"),
          );
          appendMessages(
            (m) => [
              ...m,
              {
                role: "assistant",
                content: stripDisclaimer(resp.reply),
                cards: resp.cards,
                intent: resp.intent,
                followUpQuestions: resp.follow_up_questions ?? [],
                llmUsage: resp.llm_usage ?? null,
                process: hasProcessContent(processSnapshot) ? processSnapshot : undefined,
              },
            ],
            threadId,
          );
          setFocusTabs((prevTabs) => {
            const synced = syncFocusTabsFromChat(query, resp, prevTabs, focusContext, knownSymbols);
            if (synced.activeId) {
              setActiveFocusTabId(synced.activeId);
              setCenterTab("focus");
              return synced.tabs;
            }
            return prevTabs;
          });
        }
      } catch (err) {
        // Aborted (superseded or cancelled) — not an error to surface.
        if (controller.signal.aborted) return;
        if (err instanceof TypeError && String(err).includes("Failed to fetch")) {
          appendMessages(
            (m) => [...m, { role: "assistant", content: formatChatRequestError(err, t) }],
            threadId,
          );
          return;
        }
        try {
          setStatusMsg(t("chat.streamFailed"));
          const resp = await api.chat(query, activeSessionId, resolvedOptions);
          setSessionId(resp.session_id, threadId);
          recordLlmUsage(resp.llm_usage);
          appendMessages(
            (m) => [
              ...m,
              {
                role: "assistant",
                content: stripDisclaimer(resp.reply),
                cards: resp.cards,
                intent: resp.intent,
                followUpQuestions: resp.follow_up_questions ?? [],
                llmUsage: resp.llm_usage ?? null,
              },
            ],
            threadId,
          );
          setFocusTabs((prevTabs) => {
            const synced = syncFocusTabsFromChat(query, resp, prevTabs, focusContext, knownSymbols);
            if (synced.activeId) {
              setActiveFocusTabId(synced.activeId);
              setCenterTab("focus");
              return synced.tabs;
            }
            return prevTabs;
          });
        } catch (e) {
          appendMessages(
            (m) => [...m, { role: "assistant", content: formatChatRequestError(e, t) }],
            threadId,
          );
        }
      } finally {
        // Only clear loading/status if this turn is still the active one; a
        // superseding turn manages its own lifecycle.
        if (abortRef.current === controller) {
          abortRef.current = null;
          setChatLoading(false);
          setStatusMsg("");
        }
      }
    },
    [
      appendMessages,
      focusContext,
      knownSymbols,
      pageContext,
      sessionId,
      setActiveFocusTabId,
      setCenterTab,
      setChatStream,
      setFocusTabs,
      setSessionId,
      t,
    ],
  );

  const startChatQuery = useCallback(
    (query: string, opts?: { switchTab?: boolean; context?: CopilotContext | null }) => {
      if (!query.trim() || chatLoading) return;
      if (opts?.switchTab) setCopilotOpen(true);
      setInput("");
      const turn = prepareUserTurn(query);
      void executeChat(query, undefined, opts?.context, turn);
    },
    [chatLoading, executeChat, prepareUserTurn, setCopilotOpen, setInput],
  );

  const sendChat = useCallback(() => {
    if (!input.trim() || chatLoading) return;
    startChatQuery(input.trim());
  }, [chatLoading, input, startChatQuery]);

  const analyzeHolding = useCallback(
    (h: HoldingEnriched) => {
      const q = locale === "zh" ? `分析${h.name}` : `Analyze ${h.name}`;
      const context: CopilotContext = {
        kind: "stock",
        label: `${h.name} ${h.symbol}`,
        detail: `${h.sector} · ${h.quantity}股`,
      };
      setPageContext(context);
      setCopilotOpen(true);
      startChatQuery(q, { switchTab: true, context });
    },
    [locale, setCopilotOpen, setPageContext, startChatQuery],
  );

  const runBriefingInCopilot = useCallback(
    async (userLabel: string, kind: "premarket" | "intraday" | "postmarket") => {
      if (chatLoading) return;
      setInput("");
      setChatStream(() => emptyStreamState());
      appendMessages((m) => [...m, { role: "user", content: userLabel }]);
      setChatLoading(true);
      setStatusMsg(t("portfolio.briefingLoading"));
      try {
        const raw = await api.generateBriefing(kind);
        const briefing = localizeBriefing(raw, t);
        appendMessages((m) => [
          ...m,
          { role: "assistant", content: formatBriefingMarkdown(briefing) },
        ]);
      } catch (e) {
        appendMessages((m) => [...m, { role: "assistant", content: formatChatRequestError(e, t) }]);
      } finally {
        setChatLoading(false);
        setStatusMsg("");
      }
    },
    [appendMessages, chatLoading, setChatStream, setInput, t],
  );

  const confirmChatStock = useCallback(
    (originalMessage: string, symbol: string, name: string) => {
      if (chatLoading) return;
      openFocus({ kind: "stock", symbol, name });
      appendMessages((m) => [...m, { role: "user", content: `${name}（${symbol}）` }]);
      void executeChat(originalMessage, {
        confirmedSymbol: symbol,
        confirmedName: name,
      });
    },
    [appendMessages, chatLoading, executeChat, openFocus],
  );

  const openCopilotQuery = useCallback(
    (query: string) => {
      setCopilotOpen(true);
      startChatQuery(query);
    },
    [setCopilotOpen, startChatQuery],
  );

  return {
    chatLoading,
    statusMsg,
    executeChat,
    startChatQuery,
    sendChat,
    analyzeHolding,
    runBriefingInCopilot,
    confirmChatStock,
    openCopilotQuery,
  };
}
