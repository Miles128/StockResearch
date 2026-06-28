import { useState } from "react";
import { DimensionCards, type DimensionCardItem } from "./DimensionCards";
import { parseDebateSpeech } from "./debateText";
import { stripDisclaimer } from "./disclaimerText";
import { MarkdownContent } from "./MarkdownContent";
import {
  detectDimensionSet,
  dimensionPhaseActive,
  dimensionsComplete,
  orderedDimensionSteps,
} from "./dimensionStream";
import { useI18n } from "./i18n";
import { localizeAgentDisplay, localizePositionAction } from "./uiLabels";

interface AgentStep {
  agent_id: string;
  agent_name: string;
  role: string;
  content?: string;
  status: "pending" | "running" | "done";
}

interface DebateRound {
  round: number;
  bull?: string;
  bear?: string;
  aggressive?: string;
  neutral?: string;
  neutral_view?: string;
  conservative?: string;
}

interface JudgeVerdict {
  risk_level?: string;
  position_action?: string;
  summary: string;
  reason?: string;
  divergence?: string;
  verdict?: string;
  content?: string;
  analysis_process?: string;
  holding_actions?: HoldingAction[];
}

export interface HoldingAction {
  symbol: string;
  name: string;
  action: string;
  reason: string;
  priority?: string;
}

interface StreamFeedProps {
  streamStatus: string;
  streamLog: string[];
  agentSteps: AgentStep[];
  debateRounds: DebateRound[];
  judgeVerdict: JudgeVerdict | null;
  voteTally: { bullish: number; bearish: number; neutral: number; leading?: string } | null;
  activeStreamIds?: string[];
  masterCommentary?: import("./api").MasterCommentaryItem[];
}

const DEBATE_ROLES = new Set(["bull", "bear", "aggressive", "neutral", "conservative", "vote"]);
const SUMMARY_ROLES = new Set(["manager", "judge"]);

function masterDisplayName(
  item: import("./api").MasterCommentaryItem,
  t: (key: string) => string,
): string {
  if (item.name?.trim()) return item.name;
  const key = `master.${item.master}`;
  const translated = t(key);
  return translated !== key ? translated : item.master;
}

function managerStep(steps: AgentStep[]): AgentStep | undefined {
  return steps.find((step) => step.role === "manager" || step.agent_id === "research_manager");
}

function DebateRoundMessage({
  title,
  text,
  streaming,
  className,
  expandLabel,
  collapseLabel,
  typingLabel,
}: {
  title: string;
  text: string;
  streaming?: boolean;
  className?: string;
  expandLabel: string;
  collapseLabel: string;
  typingLabel: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const parsed = parseDebateSpeech(stripDisclaimer(text));
  const collapsible = parsed.collapsible && !streaming;
  const showSummaryOnly = collapsible && !expanded;
  const body = showSummaryOnly
    ? parsed.summary
    : parsed.full || (parsed.detail ? `${parsed.summary}\n\n${parsed.detail}` : text);

  return (
    <div className={`message assistant stream-msg debate-round-msg ${className ?? ""}`.trim()}>
      <div className="stream-msg-head">
        <strong>{title}</strong>
        {streaming && <span className="muted">{typingLabel}</span>}
      </div>
      <div className="stream-msg-body">
        <MarkdownContent text={body} />
        {streaming && <span className="stream-cursor">▍</span>}
      </div>
      {collapsible && (
        <button
          type="button"
          className="btn btn-ghost btn-sm debate-expand-btn"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? collapseLabel : expandLabel}
        </button>
      )}
    </div>
  );
}

function StreamMessage({
  title,
  body,
  running,
  streaming,
  className,
  typingLabel,
  analyzingLabel,
}: {
  title: string;
  body?: string;
  running?: boolean;
  streaming?: boolean;
  className?: string;
  typingLabel: string;
  analyzingLabel: string;
}) {
  const typing = streaming ?? (running === true && body !== undefined && body !== "");
  return (
    <div className={`message assistant stream-msg ${className ?? ""}`.trim()}>
      <div className="stream-msg-head">
        <strong>{title}</strong>
        {typing && <span className="muted">{typingLabel}</span>}
        {running && !body && <span className="muted">{analyzingLabel}</span>}
      </div>
      {body !== undefined && body !== "" && (
        <div className="stream-msg-body">
          <MarkdownContent text={body} />
          {typing && <span className="stream-cursor">▍</span>}
        </div>
      )}
      {running && !body && <p className="muted">…</p>}
    </div>
  );
}

export function StreamFeed({
  streamStatus,
  streamLog,
  agentSteps,
  debateRounds,
  judgeVerdict,
  voteTally,
  activeStreamIds = [],
  masterCommentary = [],
}: StreamFeedProps) {
  const { t } = useI18n();
  const dimensionDefs = detectDimensionSet(agentSteps, streamStatus);
  const dimensionSteps = orderedDimensionSteps(agentSteps, dimensionDefs);
  const showDimensionGrid =
    dimensionPhaseActive(dimensionSteps) ||
    streamStatus.toLowerCase().includes("dimension");
  const dimsDone = dimensionsComplete(dimensionSteps);
  const manager = managerStep(agentSteps);
  const sortedRounds = debateRounds.slice().sort((a, b) => a.round - b.round);
  const isTyping = (streamId: string) => activeStreamIds.includes(streamId);
  const showDebateSection =
    sortedRounds.length > 0 ||
    voteTally != null ||
    streamStatus.toLowerCase().includes("debate") ||
    (dimsDone && judgeVerdict != null);
  const showConclusionSection =
    dimsDone &&
    (voteTally != null ||
      manager != null ||
      judgeVerdict != null ||
      streamStatus.toLowerCase().includes("judge"));
  const hasBody =
    streamLog.length > 0 ||
    showDimensionGrid ||
    showDebateSection ||
    manager != null ||
    judgeVerdict != null;

  const sideLabel: Record<string, string> = {
    bull: t("stream.long"),
    bear: t("stream.short"),
    aggressive: t("stream.aggressive"),
    neutral: t("stream.neutral"),
    conservative: t("stream.conservative"),
  };

  function debateSides(round: DebateRound): { key: string; label: string; text: string }[] {
    const sides: { key: string; label: string; text: string }[] = [];
    if (round.bull) sides.push({ key: "bull", label: sideLabel.bull, text: round.bull });
    if (round.bear) sides.push({ key: "bear", label: sideLabel.bear, text: round.bear });
    if (round.aggressive) sides.push({ key: "aggressive", label: sideLabel.aggressive, text: round.aggressive });
    const neutralText = round.neutral ?? round.neutral_view;
    if (neutralText) sides.push({ key: "neutral", label: sideLabel.neutral, text: neutralText });
    if (round.conservative) sides.push({ key: "conservative", label: sideLabel.conservative, text: round.conservative });
    return sides;
  }

  const msgProps = { typingLabel: t("stream.typing"), analyzingLabel: t("stream.analyzing") };

  return (
    <div className="stream-messages">
      {!hasBody && streamStatus && (
        <p className="stream-status stream-status-active">{streamStatus}</p>
      )}
      {!hasBody && !streamStatus && (
        <p className="stream-status muted">{t("stream.waiting")}</p>
      )}
      {!showDimensionGrid &&
        streamLog.map((line, i) => (
          <p className="stream-status muted" key={`${i}-${line.slice(0, 12)}`}>
            {line}
          </p>
        ))}
      {!showDimensionGrid && streamStatus && streamLog[streamLog.length - 1] !== streamStatus && (
        <p className="stream-status stream-status-active">{streamStatus}</p>
      )}

      {showDimensionGrid && (
        <div className="dimension-grid">
          <p className="stream-section-title">{t("stream.fourDim")}</p>
          <DimensionCards
            defaultOpen={false}
            labels={{
              confidence: t("card.confidence"),
              highlights: t("card.highlights"),
              risks: t("card.risks"),
              analyzing: t("stream.analyzing"),
            }}
            items={dimensionSteps.map(
              (step): DimensionCardItem => ({
                id: step.agent_id,
                title: localizeAgentDisplay(step.agent_id, step.agent_name, t),
                status: step.status,
                statusLabel:
                  step.status === "done"
                    ? t("stream.dimDone")
                    : step.status === "running"
                      ? t("stream.dimStarted")
                      : t("stream.dimPending"),
                body: step.content ? stripDisclaimer(step.content) : undefined,
                streaming: isTyping(step.agent_id),
              }),
            )}
          />
        </div>
      )}

      {showDebateSection && (
        <p className="stream-section-title">{t("stream.debateSection")}</p>
      )}

      {showDebateSection &&
        sortedRounds.map((round) =>
          debateSides(round).map((side) => (
            <DebateRoundMessage
              key={`${round.round}-${side.key}`}
              title={`${t("stream.round", { n: round.round })} · ${side.label}`}
              text={side.text}
              streaming={isTyping(`r${round.round}-${side.key}`)}
              className={`stream-role-${side.key}`}
              expandLabel={t("stream.expandDetail")}
              collapseLabel={t("stream.collapseDetail")}
              typingLabel={t("stream.typing")}
            />
          )),
        )}

      {showConclusionSection && (
        <p className="stream-section-title">{t("stream.conclusionSection")}</p>
      )}

      {showDebateSection && voteTally && (
        <StreamMessage
          title={t("stream.vote")}
          body={t("stream.voteBody", {
            bull: voteTally.bullish,
            bear: voteTally.bearish,
            neutral: voteTally.neutral,
            leading: voteTally.leading ? t("stream.leading", { value: voteTally.leading }) : "",
          })}
          {...msgProps}
        />
      )}

      {dimsDone && manager && (
        <StreamMessage
          key={manager.agent_id}
          title={localizeAgentDisplay(manager.agent_id, manager.agent_name, t)}
          body={manager.content}
          running={manager.status === "running"}
          streaming={isTyping(manager.agent_id)}
          className="stream-role-manager"
          {...msgProps}
        />
      )}

      {dimsDone && judgeVerdict && (
        <div className={`message assistant stream-msg stream-judge action-${localizePositionAction(judgeVerdict.position_action ?? "hold", t).toLowerCase().replace(/\s+/g, "_")}`}>
          <div className="stream-msg-head">
            <strong>{t("stream.judge")}</strong>
            {isTyping("judge") && <span className="muted">{t("stream.typing")}</span>}
          </div>
          {(judgeVerdict.risk_level || judgeVerdict.position_action) && (
            <p className="stream-msg-meta">
              {judgeVerdict.risk_level && (
                <span>{t("stream.overallRisk")}: {judgeVerdict.risk_level} </span>
              )}
              {judgeVerdict.position_action && (
                <span>
                  {t("stream.portfolioBias")}:{" "}
                  {localizePositionAction(judgeVerdict.position_action ?? "", t)}
                </span>
              )}
            </p>
          )}

          {judgeVerdict.holding_actions && judgeVerdict.holding_actions.length > 0 ? (
            <>
              {judgeVerdict.analysis_process && (
                <>
                  <p className="stream-section-title">{t("stream.process")}</p>
                  <div className="stream-msg-body">
                    <MarkdownContent text={judgeVerdict.analysis_process} />
                  </div>
                </>
              )}
              <p className="stream-section-title">
                {t("stream.perStock", { n: judgeVerdict.holding_actions.length })}
              </p>
              <div className="holding-action-list">
                {judgeVerdict.holding_actions.map((item) => (
                  <div
                    key={item.symbol}
                    className={`holding-action action-${item.action}`}
                  >
                    <div className="holding-action-head">
                      <strong>
                        {item.name}（{item.symbol}）
                      </strong>
                      <span className="holding-action-badge">
                        {localizePositionAction(item.action, t)}
                      </span>
                      {item.priority && (
                        <span className="muted holding-action-priority">
                          {t("stream.priority")} {item.priority}
                        </span>
                      )}
                    </div>
                    <div className="stream-msg-body">
                      <MarkdownContent text={item.reason} />
                    </div>
                  </div>
                ))}
              </div>
              <p className="stream-section-title">{t("stream.portfolioConclusion")}</p>
              <div className="stream-msg-body">
                <MarkdownContent text={judgeVerdict.summary} />
              </div>
              {judgeVerdict.reason && judgeVerdict.reason !== judgeVerdict.summary && (
                <div className="stream-msg-body muted">
                  <MarkdownContent text={judgeVerdict.reason} />
                </div>
              )}
              {judgeVerdict.divergence && (
                <div className="stream-msg-body muted">
                  <MarkdownContent text={`${t("stream.divergence")}: ${judgeVerdict.divergence}`} />
                </div>
              )}
            </>
          ) : (
            <>
              <div className="stream-msg-body">
                <MarkdownContent text={judgeVerdict.summary} />
                {isTyping("judge") && <span className="stream-cursor">▍</span>}
              </div>
              {judgeVerdict.reason && judgeVerdict.reason !== judgeVerdict.summary && (
                <div className="stream-msg-body muted">
                  <MarkdownContent text={judgeVerdict.reason} />
                </div>
              )}
              {judgeVerdict.divergence && (
                <div className="stream-msg-body muted">
                  <MarkdownContent text={`${t("stream.divergence")}: ${judgeVerdict.divergence}`} />
                </div>
              )}
            </>
          )}
        </div>
      )}

      {masterCommentary.length > 0 && (
        <>
          <p className="stream-section-title">{t("stream.masterCommentary")}</p>
          <div className="master-commentary-list">
            {masterCommentary.map((item, idx) => (
              <div
                key={idx}
                className={`master-commentary-item signal-${item.signal}`}
              >
                <div className="master-commentary-head">
                  <strong>{masterDisplayName(item, t)}</strong>
                  <span className={`stat-pill ${item.signal === "bullish" ? "up" : item.signal === "bearish" ? "down" : ""}`}>
                    {item.signal_text}
                  </span>
                  {item.key_metric && (
                    <span className="muted master-commentary-metric">{item.key_metric}</span>
                  )}
                </div>
                <p className="muted">{item.reasoning}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export type { AgentStep, DebateRound, JudgeVerdict };
