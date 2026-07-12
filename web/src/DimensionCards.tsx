import type { DimensionEvidence, DimensionResult } from "./api";
import { MarkdownContent } from "./MarkdownContent";

export interface DimensionCardItem {
  id: string;
  title: string;
  score?: number;
  confidence?: string;
  status?: "pending" | "running" | "done";
  statusLabel?: string;
  body?: string;
  highlights?: string[];
  risks?: string[];
  evidence?: DimensionEvidence[];
  gaps?: string[];
  partial?: boolean;
  streaming?: boolean;
}

interface DimensionCardsProps {
  items: DimensionCardItem[];
  labels: {
    confidence: string;
    highlights: string;
    risks: string;
    evidence?: string;
    gaps?: string;
    analyzing?: string;
  };
  defaultOpen?: boolean;
}

export function dimensionItemsFromResults(
  dimensions: Record<string, DimensionResult>,
  titleForKey?: (key: string, agent: string) => string,
  opts?: { brief?: boolean },
): DimensionCardItem[] {
  return Object.entries(dimensions).map(([key, dim]) => ({
    id: key,
    title: titleForKey ? titleForKey(key, dim.agent) : dim.agent || key,
    score: dim.score,
    confidence: dim.confidence,
    status: "done" as const,
    body: opts?.brief ? undefined : dim.analysis || undefined,
    highlights: opts?.brief ? (dim.highlights ?? []).slice(0, 2) : (dim.highlights ?? []),
    risks: opts?.brief ? [] : (dim.risks ?? []),
    evidence: opts?.brief ? [] : (dim.evidence ?? []),
    gaps: opts?.brief ? [] : (dim.gaps ?? []),
    partial: dim.partial,
  }));
}

export function DimensionCards({ items, labels, defaultOpen = false }: DimensionCardsProps) {
  if (!items.length) return null;
  return (
    <div className="dimension-cards-grid">
      {items.map((item) => {
        const open = defaultOpen || (item.status === "running" && item.streaming);
        return (
          <details key={item.id} className={`dimension-card-fold dimension-${item.status ?? "done"}`} open={open}>
            <summary className="dimension-card-summary">
              <span className="dimension-card-title">{item.title}</span>
              <span className="dimension-card-meta">
                {item.statusLabel ? (
                  <span className={`dimension-status dimension-status-${item.status}`}>{item.statusLabel}</span>
                ) : null}
                {item.score != null ? (
                  <span className="stat-pill">
                    {item.score}/10
                    {item.confidence ? ` · ${labels.confidence} ${item.confidence}` : ""}
                    {item.partial ? " · partial" : ""}
                  </span>
                ) : null}
              </span>
            </summary>
            <div className="dimension-card-body">
              {item.status === "running" && !item.body && !item.highlights?.length && labels.analyzing ? (
                <p className="muted dimension-card-hint">{labels.analyzing}</p>
              ) : null}
              {item.body ? (
                <div className="stream-msg-body">
                  <MarkdownContent text={item.body} />
                  {item.streaming ? <span className="stream-cursor">▍</span> : null}
                </div>
              ) : null}
              {(item.highlights?.length ?? 0) > 0 && (
                <div className="dimension-highlights">
                  <strong>{labels.highlights}：</strong>
                  <MarkdownContent
                    className="markdown-inline"
                    text={item.highlights!.join("；")}
                  />
                </div>
              )}
              {(item.risks?.length ?? 0) > 0 && (
                <div className="dimension-risks muted">
                  <strong>{labels.risks}：</strong>
                  <MarkdownContent className="markdown-inline" text={item.risks!.join("；")} />
                </div>
              )}
              {(item.evidence?.length ?? 0) > 0 && labels.evidence ? (
                <div className="dimension-evidence">
                  <strong>{labels.evidence}：</strong>
                  <ul className="dimension-evidence-list">
                    {item.evidence!.map((ev, idx) => (
                      <li key={`${ev.source}-${idx}`}>
                        {ev.url ? (
                          <a href={ev.url} target="_blank" rel="noreferrer">
                            {ev.snippet}
                          </a>
                        ) : (
                          <span>{ev.snippet}</span>
                        )}
                        <span className="muted">
                          {" "}
                          · {ev.source}
                          {ev.date ? ` · ${ev.date}` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {(item.gaps?.length ?? 0) > 0 && labels.gaps ? (
                <p className="muted dimension-gaps">
                  <strong>{labels.gaps}：</strong>
                  {item.gaps!.join("；")}
                </p>
              ) : null}
            </div>
          </details>
        );
      })}
    </div>
  );
}
