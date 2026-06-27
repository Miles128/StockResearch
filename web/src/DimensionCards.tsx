import type { DimensionResult } from "./api";
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
  streaming?: boolean;
}

interface DimensionCardsProps {
  items: DimensionCardItem[];
  labels: {
    confidence: string;
    highlights: string;
    risks: string;
    analyzing?: string;
  };
  defaultOpen?: boolean;
}

export function dimensionItemsFromResults(
  dimensions: Record<string, DimensionResult>,
  titleForKey?: (key: string, agent: string) => string,
): DimensionCardItem[] {
  return Object.entries(dimensions).map(([key, dim]) => ({
    id: key,
    title: titleForKey ? titleForKey(key, dim.agent) : dim.agent || key,
    score: dim.score,
    confidence: dim.confidence,
    status: "done" as const,
    highlights: dim.highlights ?? [],
    risks: dim.risks ?? [],
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
                <p>
                  <strong>{labels.highlights}：</strong>
                  {item.highlights!.join("；")}
                </p>
              )}
              {(item.risks?.length ?? 0) > 0 && (
                <p className="muted">
                  <strong>{labels.risks}：</strong>
                  {item.risks!.join("；")}
                </p>
              )}
            </div>
          </details>
        );
      })}
    </div>
  );
}
