import type { ReactNode } from "react";
import { processTrailLabel } from "./processKind";
import type { StreamState } from "./streamEvents";
import { useI18n } from "./i18n";

interface ProcessTrailProps {
  label?: string;
  live?: boolean;
  /** When set, summary reflects react / plan / multi-agent workflow. */
  process?: StreamState;
  children: ReactNode;
}

/** Collapsible process panel — title matches the actual agent workflow. */
export function ProcessTrail({
  label,
  live = false,
  process,
  children,
}: ProcessTrailProps) {
  const { t } = useI18n();
  const summary = processTrailLabel(process, live, t, label);
  return (
    <details className="process-trail-fold" open={live || undefined}>
      <summary className="process-trail-summary">{summary}</summary>
      <div className="process-trail-body">{children}</div>
    </details>
  );
}
