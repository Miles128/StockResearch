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
    confidenceHigh: string;
    confidenceMedium: string;
    confidenceLow: string;
    highlights: string;
    risks: string;
    evidence?: string;
    gaps?: string;
    analyzing?: string;
  };
  defaultOpen?: boolean;
}

function confidenceLabel(
  raw: string,
  labels: Pick<
    DimensionCardsProps["labels"],
    "confidenceHigh" | "confidenceMedium" | "confidenceLow"
  >,
): string {
  const key = raw.trim().toLowerCase();
  const map: Record<string, string> = {
    high: labels.confidenceHigh,
    medium: labels.confidenceMedium,
    low: labels.confidenceLow,
    高: labels.confidenceHigh,
    中: labels.confidenceMedium,
    低: labels.confidenceLow,
  };
  return map[key] ?? map[raw.trim()] ?? raw;
}

export function dimensionItemsFromResults(
  dimensions: Record<string, DimensionResult>,
  titleForKey?: (key: string, agent: string) => string,
  _opts?: { brief?: boolean },
): DimensionCardItem[] {
  // Expanded fold always shows full dimension detail (analysis + lists).
  // `brief` is ignored here; light-card brief mode only affects the summary block.
  return Object.entries(dimensions).map(([key, dim]) => ({
    id: key,
    title: titleForKey ? titleForKey(key, dim.agent) : dim.agent || key,
    score: dim.score,
    confidence: dim.confidence,
    status: "done" as const,
    body: dim.analysis || undefined,
    highlights: dim.highlights ?? [],
    risks: dim.risks ?? [],
    evidence: dim.evidence ?? [],
    gaps: dim.gaps ?? [],
    partial: dim.partial,
  }));
}

function hasDetail(item: DimensionCardItem): boolean {
  return Boolean(
    item.body ||
    (item.highlights?.length ?? 0) > 0 ||
    (item.risks?.length ?? 0) > 0 ||
    (item.evidence?.length ?? 0) > 0 ||
    (item.gaps?.length ?? 0) > 0 ||
    (item.status === "running" && item.streaming),
  );
}

export function DimensionCards({
  items,
  labels,
  defaultOpen = false,
}: DimensionCardsProps) {
  if (!items.length) return null;
  return (
    <div className="dimension-cards-grid">
      {items.map((item) => {
        const open =
          defaultOpen || (item.status === "running" && item.streaming);
        const expandable = hasDetail(item) || item.status === "running";
        return (
          <details
            key={item.id}
            className={`dimension-card-fold dimension-${item.status ?? "done"}`}
            open={open}
          >
            <summary className="dimension-card-summary">
              <span className="dimension-card-title">
                {expandable ? (
                  <span className="dimension-card-chevron" aria-hidden />
                ) : null}
                {item.title}
              </span>
              <span className="dimension-card-meta">
                {item.statusLabel ? (
                  <span
                    className={`dimension-status dimension-status-${item.status}`}
                  >
                    {item.statusLabel}
                  </span>
                ) : null}
                {item.score != null ? (
                  <span className="stat-pill">
                    {item.score}/10
                    {item.confidence
                      ? ` · ${labels.confidence} ${confidenceLabel(item.confidence, labels)}`
                      : ""}
                    {item.partial ? " · partial" : ""}
                  </span>
                ) : null}
              </span>
            </summary>
            <div className="dimension-card-body">
              {item.status === "running" &&
              !item.body &&
              !item.highlights?.length &&
              labels.analyzing ? (
                <p className="muted dimension-card-hint">{labels.analyzing}</p>
              ) : null}
              {item.body ? (
                <div className="stream-msg-body">
                  <MarkdownContent text={item.body} />
                  {item.streaming ? (
                    <span className="stream-cursor">▍</span>
                  ) : null}
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
                  <MarkdownContent
                    className="markdown-inline"
                    text={item.risks!.join("；")}
                  />
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
