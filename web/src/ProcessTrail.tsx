import type { ReactNode } from "react";
import { useI18n } from "./i18n";
import type { StreamState } from "./streamEvents";

export function hasProcessContent(process?: StreamState): boolean {
  if (!process) return false;
  return (
    process.streamLog.length > 0 ||
    process.agentSteps.length > 0 ||
    process.debateRounds.length > 0 ||
    process.judgeVerdict != null ||
    process.voteTally != null ||
    process.masterCommentary.length > 0
  );
}

interface ProcessTrailProps {
  label?: string;
  live?: boolean;
  children: ReactNode;
}

/** 默认折叠的多 Agent 思考过程容器 */
export function ProcessTrail({ label, live = false, children }: ProcessTrailProps) {
  const { t } = useI18n();
  const summary = label ?? (live ? t("chat.processLive") : t("chat.processTitle"));
  return (
    <details className="process-trail-fold">
      <summary className="process-trail-summary">{summary}</summary>
      <div className="process-trail-body">{children}</div>
    </details>
  );
}
