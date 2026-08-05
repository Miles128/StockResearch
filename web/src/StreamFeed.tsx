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
import { isRiskWorkflow, orderedRiskWorkflowSteps, riskWorkflowPhaseActive } from "./riskWorkflow";
import { useI18n } from "./i18n";
import { localizeAgentDisplay, localizePositionAction, positionActionCssClass } from "./uiLabels";
import { WorkflowAgentGrid } from "./WorkflowAgentGrid";

import type {
  AgentStep,
  DebateRound,
  HoldingAction,
  JudgeVerdict,
  VoteTally,
} from "./types/streamTypes";

export type { AgentStep, DebateRound, HoldingAction, JudgeVerdict, VoteTally };

interface StreamFeedProps {
  streamStatus: string;
  streamLog: string[];
  agentSteps: AgentStep[];
  debateRounds: DebateRound[];
  judgeVerdict: JudgeVerdict | null;
  voteTally: {
    bullish: number;
    bearish: number;
    neutral: number;
    leading?: string;
  } | null;
  activeStreamIds?: string[];
  live?: boolean;
  /** Risk tab: compact agent rail + collapsible debate/judge blocks. */
  riskCompact?: boolean;
}

const DEBATE_ROLES = new Set(["bull", "bear", "aggressive", "neutral", "conservative", "vote"]);
const SUMMARY_ROLES = new Set(["manager", "judge"]);

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

function JudgeVerdictBlock({
  judgeVerdict,
  judgeTyping,
  t,
}: {
  judgeVerdict: JudgeVerdict;
  judgeTyping: boolean;
  t: (key: string, params?: Record<string, string | number>) => string;
}) {
  return (
    <div
      className={`message assistant stream-msg stream-judge action-${positionActionCssClass(judgeVerdict.position_action ?? "仓位适中")}`}
    >
      <div className="stream-msg-head">
        <strong>{t("stream.judge")}</strong>
        {judgeTyping && <span className="muted">{t("stream.typing")}</span>}
      </div>
      {(judgeVerdict.risk_level || judgeVerdict.position_action) && (
        <p className="stream-msg-meta">
          {judgeVerdict.risk_level && (
            <span>
              {t("stream.overallRisk")}: {judgeVerdict.risk_level}{" "}
            </span>
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
                className={`holding-action action-${positionActionCssClass(item.action)}`}
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
            {judgeTyping && <span className="stream-cursor">▍</span>}
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
  live = false,
  riskCompact = false,
}: StreamFeedProps) {
  const { t } = useI18n();
  const dimensionDefs = detectDimensionSet(agentSteps, streamStatus);
  const dimensionSteps = orderedDimensionSteps(agentSteps, dimensionDefs);
  const riskWorkflow = isRiskWorkflow(agentSteps, streamStatus);
  const riskSteps = orderedRiskWorkflowSteps(agentSteps);
  const showRiskGrid = riskWorkflow && riskSteps.length > 0 && riskWorkflowPhaseActive(riskSteps);
  const showDimensionGrid =
    !showRiskGrid &&
    (dimensionPhaseActive(dimensionSteps) || streamStatus.toLowerCase().includes("dimension"));
  const dimsDone = dimensionsComplete(dimensionSteps);
  const manager = managerStep(agentSteps);
  const sortedRounds = debateRounds.slice().sort((a, b) => a.round - b.round);
  const isTyping = (streamId: string) => activeStreamIds.includes(streamId);
  const showDebateSection =
    sortedRounds.length > 0 ||
    voteTally != null ||
    streamStatus.toLowerCase().includes("debate") ||
    ((dimsDone || showRiskGrid) && judgeVerdict != null);
  const showConclusionSection =
    (dimsDone || showRiskGrid) &&
    (voteTally != null ||
      manager != null ||
      judgeVerdict != null ||
      streamStatus.toLowerCase().includes("judge"));
  const hasBody =
    streamLog.length > 0 ||
    showRiskGrid ||
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
    if (round.aggressive)
      sides.push({
        key: "aggressive",
        label: sideLabel.aggressive,
        text: round.aggressive,
      });
    const neutralText = round.neutral ?? round.neutral_view;
    if (neutralText)
      sides.push({
        key: "neutral",
        label: sideLabel.neutral,
        text: neutralText,
      });
    if (round.conservative)
      sides.push({
        key: "conservative",
        label: sideLabel.conservative,
        text: round.conservative,
      });
    return sides;
  }

  const msgProps = {
    typingLabel: t("stream.typing"),
    analyzingLabel: t("stream.analyzing"),
  };

  const visibleLog = live ? streamLog : [];
  const visibleStatus = live ? streamStatus : "";

  return (
    <div className="stream-messages">
      {!hasBody && visibleStatus && (
        <p className="stream-status stream-status-active">{visibleStatus}</p>
      )}
      {!hasBody && !visibleStatus && live && (
        <p className="stream-status muted">{t("stream.waiting")}</p>
      )}
      {!showDimensionGrid &&
        !showRiskGrid &&
        visibleLog.map((line, i) => (
          <p className="stream-status muted" key={`${i}-${line.slice(0, 12)}`}>
            {line}
          </p>
        ))}
      {!showDimensionGrid &&
        !showRiskGrid &&
        visibleStatus &&
        visibleLog[visibleLog.length - 1] !== visibleStatus && (
          <p className="stream-status stream-status-active">{visibleStatus}</p>
        )}

      {showRiskGrid && (
        <WorkflowAgentGrid
          steps={riskSteps}
          activeStreamIds={activeStreamIds}
          sectionTitle={t("stream.riskAgents")}
          compact={riskCompact}
        />
      )}

      {showDimensionGrid && (
        <div className="dimension-grid">
          <p className="stream-section-title">{t("stream.fourDim")}</p>
          <DimensionCards
            defaultOpen={false}
            labels={{
              confidence: t("card.confidence"),
              confidenceHigh: t("card.confidenceHigh"),
              confidenceMedium: t("card.confidenceMedium"),
              confidenceLow: t("card.confidenceLow"),
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

      {showDebateSection &&
        (riskCompact ? (
          <details className="risk-stream-subfold" open={live}>
            <summary className="risk-stream-subfold-summary">{t("stream.debateSection")}</summary>
            <div className="risk-stream-subfold-body">
              {sortedRounds.map((round) =>
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
              {voteTally && (
                <StreamMessage
                  title={t("stream.vote")}
                  body={t("stream.voteBody", {
                    bull: voteTally.bullish,
                    bear: voteTally.bearish,
                    neutral: voteTally.neutral,
                    leading: voteTally.leading
                      ? t("stream.leading", { value: voteTally.leading })
                      : "",
                  })}
                  {...msgProps}
                />
              )}
            </div>
          </details>
        ) : (
          <p className="stream-section-title">{t("stream.debateSection")}</p>
        ))}

      {!riskCompact &&
        showDebateSection &&
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

      {showConclusionSection && !riskCompact && (
        <p className="stream-section-title">{t("stream.conclusionSection")}</p>
      )}

      {showConclusionSection && riskCompact && (
        <details className="risk-stream-subfold" open={live && judgeVerdict == null}>
          <summary className="risk-stream-subfold-summary">{t("stream.conclusionSection")}</summary>
          <div className="risk-stream-subfold-body">
            {(dimsDone || showRiskGrid) && manager && (
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
            {(dimsDone || showRiskGrid) && judgeVerdict && (
              <JudgeVerdictBlock
                judgeVerdict={judgeVerdict}
                judgeTyping={isTyping("judge")}
                t={t}
              />
            )}
          </div>
        </details>
      )}

      {!riskCompact && showDebateSection && voteTally && (
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

      {!riskCompact && (dimsDone || showRiskGrid) && manager && (
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

      {!riskCompact && (dimsDone || showRiskGrid) && judgeVerdict && (
        <JudgeVerdictBlock judgeVerdict={judgeVerdict} judgeTyping={isTyping("judge")} t={t} />
      )}
    </div>
  );
}
