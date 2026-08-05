import { useState } from "react";
import { DimensionCards, type DimensionCardItem } from "./DimensionCards";
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

import type { AgentStep, HoldingAction, JudgeVerdict } from "./types/streamTypes";

export type { AgentStep, HoldingAction, JudgeVerdict };

interface StreamFeedProps {
  streamStatus: string;
  streamLog: string[];
  agentSteps: AgentStep[];
  judgeVerdict: JudgeVerdict | null;
  activeStreamIds?: string[];
  live?: boolean;
  /** Risk tab: compact agent rail + collapsible judge block. */
  riskCompact?: boolean;
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
  judgeVerdict,
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
  const isTyping = (streamId: string) => activeStreamIds.includes(streamId);
  const showConclusionSection =
    (dimsDone || showRiskGrid) &&
    (judgeVerdict != null || streamStatus.toLowerCase().includes("judge"));
  const hasBody = streamLog.length > 0 || showRiskGrid || showDimensionGrid || judgeVerdict != null;

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

      {showConclusionSection && !riskCompact && (
        <p className="stream-section-title">{t("stream.conclusionSection")}</p>
      )}

      {showConclusionSection && riskCompact && (
        <details className="risk-stream-subfold" open={live && judgeVerdict == null}>
          <summary className="risk-stream-subfold-summary">{t("stream.conclusionSection")}</summary>
          <div className="risk-stream-subfold-body">
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

      {!riskCompact && (dimsDone || showRiskGrid) && judgeVerdict && (
        <JudgeVerdictBlock judgeVerdict={judgeVerdict} judgeTyping={isTyping("judge")} t={t} />
      )}
    </div>
  );
}
