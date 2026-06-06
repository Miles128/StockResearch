import type { ExecutionPreference, HoldingEnriched, RouteChoiceCardData, StockChoiceCardData } from "./api";
import type { Message } from "./appTypes";
import { CardView, RouteChoiceCardView, StockChoiceCardView } from "./chatCards";
import { isResearchTurn } from "./disclaimerText";
import { useI18n } from "./i18n";
import { simpleMarkdown } from "./simpleMarkdown";
import { StreamFeed } from "./StreamFeed";
import type { StreamState } from "./streamEvents";

interface ChatPanelProps {
  messages: Message[];
  loading: boolean;
  statusMsg: string;
  chatStream: StreamState;
  input: string;
  onInputChange: (value: string) => void;
  chatExamples: { label: string; query: string }[];
  holdings: HoldingEnriched[];
  onStartQuery: (query: string) => void;
  onSend: () => void;
  onAnalyzeHolding: (h: HoldingEnriched) => void;
  onConfirmStock: (originalMessage: string, symbol: string, name: string) => void;
  onConfirmRoute: (originalMessage: string, preference: ExecutionPreference) => void;
}

export function ChatPanel({
  messages,
  loading,
  statusMsg,
  chatStream,
  input,
  onInputChange,
  chatExamples,
  holdings,
  onStartQuery,
  onSend,
  onAnalyzeHolding,
  onConfirmStock,
  onConfirmRoute,
}: ChatPanelProps) {
  const { t } = useI18n();

  return (
    <div className="panel chat-panel">
      <div className="chat-messages">
        {messages.length === 0 && !loading && (
          <div className="chat-empty">
            <p className="chat-empty-label">{t("chat.emptyHint")}</p>
            <div className="chat-example-row">
              {chatExamples.map((ex) => (
                <button key={ex.label} type="button" className="example-chip" onClick={() => onStartQuery(ex.query)}>
                  {ex.label}
                </button>
              ))}
            </div>
            {holdings.length > 0 && (
              <div className="research-quick-picks" style={{ marginTop: 8 }}>
                <span className="muted">{t("chat.holdingsQuick")}</span>
                {holdings.map((h) => (
                  <button key={h.id ?? h.symbol} type="button" className="holdings-pill" onClick={() => onAnalyzeHolding(h)}>
                    {h.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className="chat-turn">
            {m.role === "user" ? (
              <div className="message user">
                <div className="markdown-body" dangerouslySetInnerHTML={{ __html: simpleMarkdown(m.content) }} />
              </div>
            ) : (
              <>
                {m.process && (
                  <div className="message assistant process-panel">
                    <p className="process-panel-title">{t("chat.processTitle")}</p>
                    <StreamFeed
                      streamStatus={m.process.streamStatus}
                      streamLog={m.process.streamLog}
                      agentSteps={m.process.agentSteps}
                      debateRounds={m.process.debateRounds}
                      judgeVerdict={m.process.judgeVerdict}
                      voteTally={m.process.voteTally}
                      activeStreamIds={[]}
                    />
                  </div>
                )}
                {m.content.trim() && (
                  <div className="message assistant conclusion-panel">
                    <p className="process-panel-title">{t("chat.conclusion")}</p>
                    <div className="markdown-body" dangerouslySetInnerHTML={{ __html: simpleMarkdown(m.content) }} />
                  </div>
                )}
                {m.cards?.map((c, j) =>
                  c.type === "stock_choice" ? (
                    <StockChoiceCardView
                      key={j}
                      data={c.data as unknown as StockChoiceCardData}
                      disabled={loading}
                      onConfirm={onConfirmStock}
                    />
                  ) : c.type === "route_choice" ? (
                    <RouteChoiceCardView
                      key={j}
                      data={c.data as unknown as RouteChoiceCardData}
                      disabled={loading}
                      onConfirm={onConfirmRoute}
                    />
                  ) : (
                    <CardView key={j} card={c} />
                  ),
                )}
                {isResearchTurn(m.cards, m.intent) && <p className="turn-disclaimer">{t("chat.turnDisclaimer")}</p>}
              </>
            )}
          </div>
        ))}
        {loading && (
          <div className="message assistant stream-live-panel">
            <p className="process-panel-title">{t("chat.processLive")}</p>
            <StreamFeed
              streamStatus={chatStream.streamStatus || statusMsg}
              streamLog={chatStream.streamLog}
              agentSteps={chatStream.agentSteps}
              debateRounds={chatStream.debateRounds}
              judgeVerdict={chatStream.judgeVerdict}
              voteTally={chatStream.voteTally}
              activeStreamIds={chatStream.activeStreamIds}
            />
          </div>
        )}
      </div>
      <div className="chat-footer">
        <div className="chat-input-row">
          <input
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onSend()}
            placeholder={t("chat.placeholder")}
          />
          <button className="btn btn-primary" onClick={onSend} disabled={loading}>
            {loading ? t("chat.sending") : t("chat.send")}
          </button>
        </div>
      </div>
    </div>
  );
}
