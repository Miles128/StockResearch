import { useCallback, useState } from "react";
import { api, type AgentStreamEvent, type ChatResponse, type ChatStreamOptions, type ExecutionPreference } from "../api";
import { stripDisclaimer } from "../disclaimerText";
import { useI18n } from "../i18n";
import { applyStreamEvent, emptyStreamState } from "../streamEvents";
import { normalizeStreamEvent } from "../streamI18n";
import type { Message } from "../appTypes";

export interface ChatState {
  messages: Message[];
  input: string;
  setInput: (value: string) => void;
  sessionId: string | undefined;
  chatLoading: boolean;
  statusMsg: string;
  chatStream: ReturnType<typeof emptyStreamState>;
  executeChat: (query: string, options?: ChatStreamOptions) => Promise<void>;
  startChatQuery: (query: string, opts?: { switchTab?: boolean }) => void;
  sendChat: () => void;
  confirmChatStock: (originalMessage: string, symbol: string, name: string) => void;
  confirmChatRoute: (originalMessage: string, preference: ExecutionPreference) => void;
}

export function useChat(onSwitchTab?: (tab: "chat") => void): ChatState {
  const { t } = useI18n();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [chatLoading, setChatLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [chatStream, setChatStream] = useState(emptyStreamState());

  const executeChat = useCallback(
    async (query: string, options?: ChatStreamOptions) => {
      setChatLoading(true);
      setStatusMsg(t("chat.connecting"));
      setChatStream(emptyStreamState());
      let processSnapshot = emptyStreamState();
      try {
        const resp = await api.chatStream(
          query,
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
          const assistantMsg: Message = {
            role: "assistant",
            content: stripDisclaimer(resp.reply),
            cards: resp.cards,
            intent: resp.intent,
            llmUsage: resp.llm_usage ?? null,
          };
          setMessages((m) => [...m, assistantMsg]);
        }
      } catch {
        try {
          setStatusMsg(t("chat.streamFailed"));
          const resp = await api.chat(query, sessionId, options);
          setSessionId(resp.session_id);
          setMessages((m) => [
            ...m,
            {
              role: "assistant",
              content: stripDisclaimer(resp.reply),
              cards: resp.cards,
              intent: resp.intent,
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
    [sessionId, statusMsg, t],
  );

  const startChatQuery = useCallback(
    (query: string, opts?: { switchTab?: boolean }) => {
      if (!query.trim() || chatLoading) return;
      if (opts?.switchTab) onSwitchTab?.("chat");
      setInput("");
      setMessages((m) => [...m, { role: "user", content: query }]);
      void executeChat(query);
    },
    [chatLoading, executeChat, onSwitchTab],
  );

  const sendChat = useCallback(() => {
    if (!input.trim() || chatLoading) return;
    startChatQuery(input.trim());
  }, [input, chatLoading, startChatQuery]);

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
    executeChat,
    startChatQuery,
    sendChat,
    confirmChatStock,
    confirmChatRoute,
  };
}
