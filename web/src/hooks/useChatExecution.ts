import { useCallback, useState } from "react";
import {
  api,
  type AgentStreamEvent,
  type ChatStreamOptions,
  type ExecutionPreference,
  type HoldingEnriched,
} from "../api";
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
  setSessionId: (id: string) => void;
  pageContext: CopilotContext | null;
  focusContext: FocusContext | null;
  knownSymbols: KnownSymbol[];
  appendMessages: (updater: (messages: Message[]) => Message[]) => void;
  input: string;
  setInput: (value: string) => void;
  setChatStream: (updater: (prev: StreamState) => StreamState) => void;
  setFocusTabs: (updater: (tabs: FocusTab[]) => FocusTab[]) => void;
  setActiveFocusTabId: (id: string | null) => void;
  setCenterTab: (tab: "focus" | "risk" | "news") => void;
  setCopilotOpen: (open: boolean) => void;
  setPageContext: (ctx: CopilotContext | null) => void;
  openFocus: (context: FocusContext) => void;
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
  runBriefingInCopilot: (userLabel: string, kind: "intraday" | "postmarket") => Promise<void>;
  confirmChatStock: (originalMessage: string, symbol: string, name: string) => void;
  confirmChatRoute: (originalMessage: string, preference: ExecutionPreference) => void;
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

  const executeChat = useCallback(
    async (
      query: string,
      chatOptions?: ChatStreamOptions,
      contextOverride?: CopilotContext | null,
    ) => {
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
          sessionId,
          (event: AgentStreamEvent) => {
            if (event.type === "analysis_choice" || event.type === "stock_choice") return;
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
        );
        if (resp) {
          setSessionId(resp.session_id);
          processSnapshot = finalizeStreamState(
            { ...processSnapshot, streamStatus: t("chat.analysisDone") },
            t("chat.analysisDone"),
          );
          appendMessages((m) => [
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
          ]);
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
        if (err instanceof TypeError && String(err).includes("Failed to fetch")) {
          appendMessages((m) => [
            ...m,
            { role: "assistant", content: formatChatRequestError(err, t) },
          ]);
          return;
        }
        try {
          setStatusMsg(t("chat.streamFailed"));
          const resp = await api.chat(query, sessionId, resolvedOptions);
          setSessionId(resp.session_id);
          appendMessages((m) => [
            ...m,
            {
              role: "assistant",
              content: stripDisclaimer(resp.reply),
              cards: resp.cards,
              intent: resp.intent,
              followUpQuestions: resp.follow_up_questions ?? [],
              llmUsage: resp.llm_usage ?? null,
            },
          ]);
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
          appendMessages((m) => [
            ...m,
            { role: "assistant", content: formatChatRequestError(e, t) },
          ]);
        }
      } finally {
        setChatLoading(false);
        setStatusMsg("");
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
      appendMessages((m) => [...m, { role: "user", content: query }]);
      void executeChat(query, undefined, opts?.context);
    },
    [appendMessages, chatLoading, executeChat, setCopilotOpen, setInput],
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
    async (userLabel: string, kind: "intraday" | "postmarket") => {
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
        appendMessages((m) => [
          ...m,
          { role: "assistant", content: formatChatRequestError(e, t) },
        ]);
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
      void executeChat(originalMessage, { confirmedSymbol: symbol, confirmedName: name });
    },
    [appendMessages, chatLoading, executeChat, openFocus],
  );

  const confirmChatRoute = useCallback(
    (originalMessage: string, preference: ExecutionPreference) => {
      if (chatLoading) return;
      const labels: Record<ExecutionPreference, string> = {
        react: t("chat.routeReact"),
        plan_execute: t("chat.routePlan"),
        preset: t("chat.routePreset"),
        auto: t("chat.routeAuto"),
      };
      appendMessages((m) => [
        ...m,
        { role: "user", content: t("chat.selectedMode", { mode: labels[preference] }) },
      ]);
      void executeChat(originalMessage, { executionPreference: preference });
    },
    [appendMessages, chatLoading, executeChat, t],
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
    confirmChatRoute,
    openCopilotQuery,
  };
}
