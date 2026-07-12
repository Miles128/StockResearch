import type { DimensionEvidence, DimensionResult } from "./api";
import { MarkdownContent } from "./MarkdownContent";
import {
  circledIndex,
  LineNumberedDoc,
  textToLineRows,
  type LineDocRow,
} from "./lineNumberedDoc";

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

function itemToRows(item: DimensionCardItem, index: number, labels: DimensionCardsProps["labels"]): LineDocRow[] {
  const rows: LineDocRow[] = [];
  const title = `${circledIndex(index)} ${item.title}`;
  const metaBits: string[] = [];
  if (item.statusLabel) metaBits.push(item.statusLabel);
  if (item.score != null) {
    metaBits.push(
      `${item.score}/10${item.confidence ? ` · ${labels.confidence} ${item.confidence}` : ""}${
        item.partial ? " · partial" : ""
      }`,
    );
  }
  rows.push({
    kind: "section",
    text: title,
    meta: metaBits.length ? metaBits.join(" · ") : undefined,
  });

  const analyzing =
    item.status === "running" && !item.body && !(item.highlights?.length ?? 0) && labels.analyzing;
  if (analyzing) {
    rows.push({ kind: "text", text: labels.analyzing! });
  }

  if (item.body) {
    const bodyRows = textToLineRows(item.body);
    if (bodyRows.length) {
      const last = bodyRows[bodyRows.length - 1];
      rows.push(...bodyRows.slice(0, -1));
      rows.push({
        kind: "node",
        node: (
          <span className="ln-body-line">
            {last.text}
            {item.streaming ? <span className="stream-cursor">▍</span> : null}
          </span>
        ),
      });
    } else {
      rows.push({
        kind: "node",
        node: (
          <div className="stream-msg-body ln-md">
            <MarkdownContent text={item.body} />
            {item.streaming ? <span className="stream-cursor">▍</span> : null}
          </div>
        ),
      });
    }
  }

  for (const h of item.highlights ?? []) {
    rows.push({ kind: "text", text: h });
  }
  for (const r of item.risks ?? []) {
    rows.push({ kind: "text", text: `${labels.risks}：${r}` });
  }
  if ((item.evidence?.length ?? 0) > 0 && labels.evidence) {
    for (const ev of item.evidence!) {
      const suffix = `${ev.source}${ev.date ? ` · ${ev.date}` : ""}`;
      rows.push({ kind: "text", text: `${ev.snippet} · ${suffix}` });
    }
  }
  if ((item.gaps?.length ?? 0) > 0 && labels.gaps) {
    rows.push({ kind: "text", text: `${labels.gaps}：${item.gaps!.join("；")}` });
  }

  return rows;
}

export function DimensionCards({ items, labels }: DimensionCardsProps) {
  if (!items.length) return null;

  const rows: LineDocRow[] = [];
  items.forEach((item, index) => {
    if (index > 0) rows.push({ kind: "spacer" });
    rows.push(...itemToRows(item, index, labels));
  });

  return <LineNumberedDoc className="dimension-line-doc" rows={rows} />;
}
