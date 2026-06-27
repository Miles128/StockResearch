import { useCallback, useState } from "react";
import {
  api,
  type AgentStreamEvent,
  type ChatStreamOptions,
  type ExecutionPreference,
} from "../api";
import type { CopilotContext, Message } from "../appTypes";
import { stripDisclaimer } from "../disclaimerText";
import { useI18n } from "../i18n";
import { applyStreamEvent, emptyStreamState } from "../streamEvents";
import { normalizeStreamEvent } from "../streamI18n";

export interface CopilotChatState {
  messages: Message[];
  input: string;
  setInput: (value: string) => void;
  sessionId: string | undefined;
  chatLoading: boolean;
  statusMsg: string;
  chatStream: ReturnType<typeof emptyStreamState>;
  startChatQuery: (
    query: string,
    opts?: { switchTab?: boolean; context?: CopilotContext | null },
  ) => void;
  sendChat: () => void;
  analyzeHolding: (holding: { name: string; symbol: string; sector: string; quantity: number }) => void;
  askCopilot: (query: string, context: CopilotContext) => void;
  newCopilotThread: () => void;
  confirmChatStock: (originalMessage: string, symbol: string, name: string) => void;
  confirmChatRoute: (originalMessage: string, preference: ExecutionPreference) => void;
}

interface UseCopilotChatOptions {
  pageContext: CopilotContext | null;
  onOpenCopilot: () => void;
  onSetPageContext?: (context: CopilotContext) => void;
  locale: "zh" | "en";
}

export function useCopilotChat({
  pageContext,
  onOpenCopilot,
  onSetPageContext,
  locale,
}: UseCopilotChatOptions): CopilotChatState {
  const { t } = useI18n();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [chatLoading, setChatLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [chatStream, setChatStream] = useState(emptyStreamState());

  const executeChat = useCallback(
    async (
      query: string,
      options?: ChatStreamOptions,
      contextOverride?: CopilotContext | null,
    ) => {
      setChatLoading(true);
      setStatusMsg(t("chat.connecting"));
      setChatStream(emptyStreamState());
      let processSnapshot = emptyStreamState();
      const activeContext = contextOverride === undefined ? pageContext : contextOverride;
      const requestQuery = activeContext
        ? `${query}\n\n[当前画布上下文：${activeContext.label}${activeContext.detail ? `；${activeContext.detail}` : ""}]`
        : query;
      try {
        const resp = await api.chatStream(
          requestQuery,
          sessionId,
          (event: AgentStreamEvent) => {
            if (
              event.type === "analysis_choice" ||
              event.type === "stock_choice" ||
              event.type === "route_choice"
            ) {
              return;
            }
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
          options,
        );
        if (resp) {
          setSessionId(resp.session_id);
          processSnapshot = {
            ...processSnapshot,
            streamStatus: processSnapshot.streamStatus || statusMsg || t("chat.analysisDone"),
          };
          const hasResearchCard = resp.cards?.some((c) => c.type === "research");
          const hasProcessTrail =
            processSnapshot.streamLog.length > 0 ||
            processSnapshot.agentSteps.length > 0 ||
            processSnapshot.debateRounds.length > 0 ||
            processSnapshot.judgeVerdict != null;
          setMessages((m) => [
            ...m,
            {
              role: "assistant",
              content: stripDisclaimer(resp.reply),
              cards: resp.cards,
              intent: resp.intent,
              followUpQuestions: resp.follow_up_questions ?? [],
              llmUsage: resp.llm_usage ?? null,
              process: hasProcessTrail || hasResearchCard ? processSnapshot : undefined,
            },
          ]);
        }
      } catch {
        try {
          setStatusMsg(t("chat.streamFailed"));
          const resp = await api.chat(requestQuery, sessionId, options);
          setSessionId(resp.session_id);
          setMessages((m) => [
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
        } catch (e) {
          setMessages((m) => [...m, { role: "assistant", content: `Error: ${String(e)}` }]);
        }
      } finally {
        setChatLoading(false);
        setStatusMsg("");
      }
    },
    [pageContext, sessionId, statusMsg, t],
  );

  const startChatQuery = useCallback(
    (query: string, opts?: { switchTab?: boolean; context?: CopilotContext | null }) => {
      if (!query.trim() || chatLoading) return;
      if (opts?.switchTab) onOpenCopilot();
      setInput("");
      setMessages((m) => [...m, { role: "user", content: query }]);
      void executeChat(query, undefined, opts?.context);
    },
    [chatLoading, executeChat, onOpenCopilot],
  );

  const sendChat = useCallback(() => {
    if (!input.trim() || chatLoading) return;
    startChatQuery(input.trim());
  }, [input, chatLoading, startChatQuery]);

  const analyzeHolding = useCallback(
    (h: { name: string; symbol: string; sector: string; quantity: number }) => {
      const q = locale === "zh" ? `分析${h.name}` : `Analyze ${h.name}`;
      const context: CopilotContext = {
        kind: "stock",
        label: `${h.name} ${h.symbol}`,
        detail: `${h.sector} · ${h.quantity}股`,
      };
      onSetPageContext?.(context);
      startChatQuery(q, { switchTab: true, context });
    },
    [locale, onSetPageContext, startChatQuery],
  );

  const askCopilot = useCallback(
    (query: string, context: CopilotContext) => {
      onSetPageContext?.(context);
      onOpenCopilot();
      startChatQuery(query, { context });
    },
    [onOpenCopilot, onSetPageContext, startChatQuery],
  );

  const newCopilotThread = useCallback(() => {
    setMessages([]);
    setSessionId(undefined);
    setChatStream(emptyStreamState());
    setStatusMsg("");
    setInput("");
  }, []);

  const confirmChatStock = useCallback(
    (originalMessage: string, symbol: string, name: string) => {
      if (chatLoading) return;
      setMessages((m) => [...m, { role: "user", content: `${name}（${symbol}）` }]);
      void executeChat(originalMessage, { confirmedSymbol: symbol, confirmedName: name });
    },
    [chatLoading, executeChat],
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
      setMessages((m) => [
        ...m,
        { role: "user", content: t("chat.selectedMode", { mode: labels[preference] }) },
      ]);
      void executeChat(originalMessage, { executionPreference: preference });
    },
    [chatLoading, executeChat, t],
  );

  return {
    messages,
    input,
    setInput,
    sessionId,
    chatLoading,
    statusMsg,
    chatStream,
    startChatQuery,
    sendChat,
    analyzeHolding,
    askCopilot,
    newCopilotThread,
    confirmChatStock,
    confirmChatRoute,
  };
}
