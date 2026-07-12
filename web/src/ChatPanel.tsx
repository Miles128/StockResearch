import type { ExecutionPreference, HoldingEnriched, StockChoiceCardData } from "./api";
import type { Message } from "./appTypes";
import type { AppMode } from "./modeSettings";
import { CardView, PlanCardsFold, StockChoiceCardView } from "./chatCards";
import { FollowUpChips } from "./FollowUpChips";
import { LightResearchCard } from "./LightResearchCard";
import {
  findResearchReport,
  FollowUpQuestions,
} from "./researchReportView";
import { isResearchTurn } from "./disclaimerText";
import { useI18n } from "./i18n";
import { MarkdownContent } from "./MarkdownContent";
import { ProcessTrail } from "./ProcessTrail";
import { skillStepLabel } from "./processKind";
import { CollapsibleSection } from "./CollapsibleSection";
import { cardsWithoutReplyDuplicate, shouldHideReplyBubble } from "./replyCardDedup";
import { StreamFeed } from "./StreamFeed";
import type { StreamState } from "./streamEvents";
import { hasLiveProcessContent, hasProcessContent } from "./streamEvents";

interface ChatPanelProps {
  messages: Message[];
  loading: boolean;
  statusMsg: string;
  chatStream: StreamState;
  input: string;
  onInputChange: (value: string) => void;
  chatExamples: { label: string; query: string }[];
  holdings: HoldingEnriched[];
  appMode: AppMode;
  onStartQuery: (query: string) => void;
  onSend: () => void;
  onAnalyzeHolding: (h: HoldingEnriched) => void;
  onConfirmStock: (originalMessage: string, symbol: string, name: string) => void;
  onConfirmRoute: (originalMessage: string, preference: ExecutionPreference) => void;
}

function ProcessStreamFeed({
  process,
  statusMsg,
  live = false,
}: {
  process: StreamState;
  statusMsg: string;
  live?: boolean;
}) {
  const { t } = useI18n();
  const topHasBody =
    process.streamLog.length > 0 ||
    process.agentSteps.length > 0 ||
    process.debateRounds.length > 0 ||
    process.judgeVerdict != null ||
    process.voteTally != null ||
    process.masterCommentary.length > 0;
  const singleSkill = process.skillSteps.length === 1 && !topHasBody;

  return (
    <ProcessTrail live={live} process={process}>
      {process.skillSteps.map((skill) =>
        singleSkill ? (
          <StreamFeed
            key={skill.skillRunId}
            streamStatus={skill.nested.streamStatus || statusMsg}
            streamLog={skill.nested.streamLog}
            agentSteps={skill.nested.agentSteps}
            debateRounds={skill.nested.debateRounds}
            judgeVerdict={skill.nested.judgeVerdict}
            voteTally={skill.nested.voteTally}
            masterCommentary={skill.nested.masterCommentary}
            activeStreamIds={skill.nested.activeStreamIds}
            live={live}
          />
        ) : (
          <CollapsibleSection
            key={skill.skillRunId}
            title={skillStepLabel(skill, t)}
            summary={
              skill.status === "running"
                ? "…"
                : skill.summary?.slice(0, 80) ?? t("chat.processDone")
            }
            defaultCollapsed={skill.status === "done"}
            className="skill-process-block"
          >
            <StreamFeed
              streamStatus={skill.nested.streamStatus || statusMsg}
              streamLog={skill.nested.streamLog}
              agentSteps={skill.nested.agentSteps}
              debateRounds={skill.nested.debateRounds}
              judgeVerdict={skill.nested.judgeVerdict}
              voteTally={skill.nested.voteTally}
              masterCommentary={skill.nested.masterCommentary}
              activeStreamIds={skill.nested.activeStreamIds}
              live={live}
            />
          </CollapsibleSection>
        ),
      )}
      {topHasBody && (
        <StreamFeed
          streamStatus={process.streamStatus || statusMsg}
          streamLog={process.streamLog}
          agentSteps={process.agentSteps}
          debateRounds={process.debateRounds}
          judgeVerdict={process.judgeVerdict}
          voteTally={process.voteTally}
          masterCommentary={process.masterCommentary}
          activeStreamIds={process.activeStreamIds}
          live={live}
        />
      )}
    </ProcessTrail>
  );
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
  appMode,
  onStartQuery,
  onSend,
  onAnalyzeHolding,
  onConfirmStock,
  onConfirmRoute,
}: ChatPanelProps) {
  const { t } = useI18n();

  function renderAssistantConclusion(m: Message) {
    const researchReport = findResearchReport(m.cards);
    const hideReply = shouldHideReplyBubble(m.cards);
    const showConclusionShell = isResearchTurn(m.cards, m.intent) && !researchReport;

    if (hideReply || !m.content.trim()) return null;

    if (showConclusionShell) {
      return (
        <div className="message assistant conclusion-panel">
          <p className="process-panel-title">{t("chat.conclusion")}</p>
          <MarkdownContent text={m.content} />
        </div>
      );
    }

    return (
      <div className="message assistant">
        <MarkdownContent text={m.content} />
      </div>
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
                <MarkdownContent text={m.content} />
              </div>
            ) : (
              <>
                {renderAssistantConclusion(m)}
                {(() => {
                  const researchReport = findResearchReport(m.cards);
                  const visibleCards = cardsWithoutReplyDuplicate(m.cards, m.content);
                  if (researchReport) {
                    return (
                      <LightResearchCard
                        report={researchReport}
                        appMode={appMode}
                        onFollowUp={onStartQuery}
                      />
                    );
                  }
                  return (
                    <>
                      {visibleCards && <PlanCardsFold cards={visibleCards} />}
                      {visibleCards?.map((c, j) =>
                    c.type === "stock_choice" ? (
                      <StockChoiceCardView
                        key={j}
                        data={c.data as unknown as StockChoiceCardData}
                        disabled={loading}
                        onConfirm={onConfirmStock}
                      />
                    ) : (
                      <CardView key={j} card={c} />
                    ),
                  )}
                    </>
                  );
                })()}
                {hasProcessContent(m.process) && m.process && (
                  <ProcessStreamFeed process={m.process} statusMsg={statusMsg} />
                )}
                {!findResearchReport(m.cards) && m.followUpQuestions && m.followUpQuestions.length > 0 && (
                  <FollowUpChips questions={m.followUpQuestions} onSelect={onStartQuery} />
                )}
                {m.role === "assistant" && (
                  <p className="turn-disclaimer">{t("chat.turnDisclaimer")}</p>
                )}
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
        {loading && (hasLiveProcessContent(chatStream) || statusMsg) && (
          <div className="message assistant stream-live-panel">
            <ProcessStreamFeed process={chatStream} statusMsg={statusMsg} live />
          </div>
        )}
      </div>
      <div className="chat-footer">
        <div className="chat-input-composer">
          <textarea
            className="chat-input-textarea"
            rows={3}
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            placeholder={t("chat.placeholder")}
          />
          <button
            type="button"
            className="chat-send-icon"
            onClick={onSend}
            disabled={loading || !input.trim()}
            title={loading ? t("chat.sending") : t("chat.send")}
            aria-label={t("chat.send")}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M5 12h14M13 6l6 6-6 6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
