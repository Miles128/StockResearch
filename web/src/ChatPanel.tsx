import type { ExecutionPreference, GlossaryTerm, HoldingEnriched, RouteChoiceCardData, StockChoiceCardData } from "./api";
import type { Message } from "./appTypes";
import type { AppMode } from "./modeSettings";
import { CardView, RouteChoiceCardView, StockChoiceCardView } from "./chatCards";
import { FollowUpChips } from "./FollowUpChips";
import { LightResearchCard } from "./LightResearchCard";
import {
  findResearchReport,
  FollowUpQuestions,
} from "./researchReportView";
import { isResearchTurn } from "./disclaimerText";
import { useI18n } from "./i18n";
import { MarkdownContent } from "./MarkdownContent";
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
  enableGlossary: boolean;
  appMode: AppMode;
  glossary: Record<string, GlossaryTerm>;
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
  enableGlossary,
  appMode,
  glossary,
  onStartQuery,
  onSend,
  onAnalyzeHolding,
  onConfirmStock,
  onConfirmRoute,
}: ChatPanelProps) {
  const { t } = useI18n();
  const markdownProps = { enableGlossary, glossary };

  function renderAssistantContent(m: Message) {
    const showConclusionShell = isResearchTurn(m.cards, m.intent);

    return (
      <>
        {m.content.trim() &&
          (showConclusionShell ? (
            <div className="message assistant conclusion-panel">
              <p className="process-panel-title">{t("chat.conclusion")}</p>
              <MarkdownContent text={m.content} {...markdownProps} />
            </div>
          ) : (
            <div className="message assistant">
              <MarkdownContent text={m.content} {...markdownProps} />
            </div>
          ))}
      </>
    );
  }

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
                <MarkdownContent text={m.content} {...markdownProps} />
              </div>
            ) : (
              <>
                {renderAssistantContent(m)}
                {(() => {
                  const researchReport = findResearchReport(m.cards);
                  if (researchReport) {
                    return (
                      <LightResearchCard
                        report={researchReport}
                        appMode={appMode}
                        onFollowUp={onStartQuery}
                      />
                    );
                  }
                  return m.cards?.map((c, j) =>
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
                  );
                })()}
                {!findResearchReport(m.cards) && m.followUpQuestions && m.followUpQuestions.length > 0 && (
                  <FollowUpChips questions={m.followUpQuestions} onSelect={onStartQuery} />
                )}
                {isResearchTurn(m.cards, m.intent) && <p className="turn-disclaimer">{t("chat.turnDisclaimer")}</p>}
                {!loading &&
                  i === messages.length - 1 &&
                  findResearchReport(m.cards) != null &&
                  (() => {
                    const fr = findResearchReport(m.cards);
                    return fr ? <FollowUpQuestions report={fr} onAsk={onStartQuery} /> : null;
                  })()}
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
