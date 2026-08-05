import { useEffect, useState, type ReactNode } from "react";
import { MarkdownContent } from "./MarkdownContent";
import { localizeAgentDisplay } from "./uiLabels";
import { useI18n } from "./i18n";
import type { AgentStep } from "./types/streamTypes";
import { IconAlert, IconBolt, IconChart, IconList, IconMessages } from "./ui/Icons";

function AgentWorkflowIcon({ agentId, size = 16 }: { agentId: string; size?: number }) {
  const props = { size, className: "ui-icon workflow-agent-icon" };
  switch (agentId) {
    case "rules":
      return <IconAlert {...props} />;
    case "market":
      return <IconChart {...props} />;
    case "correlation":
      return <IconList {...props} />;
    case "scenario":
      return <IconBolt {...props} />;
    case "research_manager":
      return <IconMessages {...props} />;
    case "judge":
      return <IconAlert {...props} />;
    default:
      return <IconBolt {...props} />;
  }
}

function statusLabel(status: AgentStep["status"], t: (key: string) => string): string {
  if (status === "done") return t("stream.dimDone");
  if (status === "running") return t("stream.dimStarted");
  return t("stream.dimPending");
}

function shortAgentLabel(agentId: string, fullName: string): string {
  const map: Record<string, string> = {
    rules: "规则",
    market: "市场",
    correlation: "相关",
    scenario: "情景",
    research_manager: "RM",
    judge: "裁判",
  };
  return map[agentId] ?? (fullName.length <= 4 ? fullName : fullName.slice(0, 2));
}

interface WorkflowAgentGridProps {
  steps: AgentStep[];
  activeStreamIds?: string[];
  sectionTitle?: ReactNode;
  /** Icon rail + click-to-expand details (default for risk tab). */
  compact?: boolean;
}

export function WorkflowAgentGrid({
  steps,
  activeStreamIds = [],
  sectionTitle,
  compact = true,
}: WorkflowAgentGridProps) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    // running 步骤自动展开：基于 steps 的状态同步，属预期级联
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setExpanded((prev) => {
      const next = new Set(prev);
      for (const step of steps) {
        if (step.status === "running") next.add(step.agent_id);
      }
      return next;
    });
  }, [steps]);

  if (!steps.length) return null;

  const doneCount = steps.filter((s) => s.status === "done").length;

  function toggleAgent(agentId: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(agentId)) next.delete(agentId);
      else next.add(agentId);
      return next;
    });
  }

  if (!compact) {
    return (
      <div className="workflow-agent-grid-wrap">
        {sectionTitle ? <p className="stream-section-title">{sectionTitle}</p> : null}
        <div className="dimension-cards-grid workflow-agent-grid">
          {steps.map((step) => {
            const streaming = activeStreamIds.includes(step.agent_id);
            const title = localizeAgentDisplay(step.agent_id, step.agent_name, t);
            return (
              <details
                key={step.agent_id}
                className={`dimension-card-fold workflow-agent-card dimension-${step.status ?? "done"} stream-role-${step.role ?? step.agent_id}`}
                open={step.status === "running"}
              >
                <summary className="dimension-card-summary workflow-agent-summary">
                  <span className="workflow-agent-title-wrap">
                    <AgentWorkflowIcon agentId={step.agent_id} />
                    <span className="dimension-card-title">{title}</span>
                  </span>
                  <span className={`dimension-status dimension-status-${step.status}`}>
                    {statusLabel(step.status, t)}
                  </span>
                </summary>
                <AgentStepBody step={step} streaming={streaming} t={t} />
              </details>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="workflow-agent-compact">
      <div className="workflow-agent-compact-head">
        {sectionTitle ? <span className="workflow-agent-compact-title">{sectionTitle}</span> : null}
        <span className="workflow-agent-progress muted">
          {t("risk.agentProgress", { done: doneCount, total: steps.length })}
        </span>
      </div>
      <div
        className="workflow-agent-rail"
        role="tablist"
        aria-label={String(sectionTitle ?? t("stream.riskAgents"))}
      >
        {steps.map((step) => {
          const title = localizeAgentDisplay(step.agent_id, step.agent_name, t);
          const isOpen = expanded.has(step.agent_id);
          const streaming = activeStreamIds.includes(step.agent_id);
          return (
            <button
              key={step.agent_id}
              type="button"
              role="tab"
              aria-selected={isOpen}
              aria-expanded={isOpen}
              title={title}
              className={`workflow-agent-chip dimension-${step.status ?? "pending"} stream-role-${step.role ?? step.agent_id}${isOpen ? " is-open" : ""}${streaming ? " is-streaming" : ""}`}
              onClick={() => toggleAgent(step.agent_id)}
            >
              <AgentWorkflowIcon agentId={step.agent_id} size={14} />
              <span className="workflow-agent-chip-label">
                {shortAgentLabel(step.agent_id, title)}
              </span>
              <span className={`workflow-agent-chip-dot status-${step.status}`} aria-hidden />
            </button>
          );
        })}
      </div>
      <div className="workflow-agent-details">
        {steps.map((step) => {
          if (!expanded.has(step.agent_id)) return null;
          const streaming = activeStreamIds.includes(step.agent_id);
          const title = localizeAgentDisplay(step.agent_id, step.agent_name, t);
          return (
            <details
              key={step.agent_id}
              className={`workflow-agent-detail dimension-${step.status ?? "done"} stream-role-${step.role ?? step.agent_id}`}
              open
            >
              <summary className="workflow-agent-detail-summary">
                <span className="workflow-agent-title-wrap">
                  <AgentWorkflowIcon agentId={step.agent_id} size={14} />
                  <strong>{title}</strong>
                </span>
                <span className={`dimension-status dimension-status-${step.status}`}>
                  {statusLabel(step.status, t)}
                </span>
              </summary>
              <AgentStepBody step={step} streaming={streaming} t={t} />
            </details>
          );
        })}
      </div>
    </div>
  );
}

function AgentStepBody({
  step,
  streaming,
  t,
}: {
  step: AgentStep;
  streaming: boolean;
  t: (key: string) => string;
}) {
  return (
    <div className="dimension-card-body workflow-agent-detail-body">
      {step.status === "running" && !step.content && (
        <p className="muted dimension-card-hint">{t("stream.analyzing")}</p>
      )}
      {step.content ? (
        <div className="stream-msg-body">
          <MarkdownContent text={step.content} />
          {streaming ? <span className="stream-cursor">▍</span> : null}
        </div>
      ) : null}
    </div>
  );
}
