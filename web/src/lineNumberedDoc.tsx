import type { ReactNode } from "react";

export const CIRCLED_NUMBERS = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"] as const;

export type LineDocRow =
  | { kind: "section"; text: string; meta?: ReactNode }
  | { kind: "text"; text: string; onClick?: () => void }
  | { kind: "spacer" }
  | { kind: "node"; node: ReactNode };

interface LineNumberedDocProps {
  rows: LineDocRow[];
  /** Start numbering at this value (default 1). */
  startAt?: number;
  className?: string;
}

/** Terminal-style line gutter: every row (including spacers) gets a number. */
export function LineNumberedDoc({ rows, startAt = 1, className }: LineNumberedDocProps) {
  if (!rows.length) return null;
  let n = startAt;
  return (
    <div className={`line-numbered-doc${className ? ` ${className}` : ""}`} role="list">
      {rows.map((row, i) => {
        const lineNo = n++;
        if (row.kind === "spacer") {
          return (
            <div key={`sp-${i}`} className="ln-row ln-spacer" role="listitem">
              <span className="ln-n" aria-hidden>
                {lineNo}
              </span>
              <span className="ln-c" />
            </div>
          );
        }
        if (row.kind === "section") {
          return (
            <div key={`sec-${i}`} className="ln-row ln-section" role="listitem">
              <span className="ln-n" aria-hidden>
                {lineNo}
              </span>
              <span className="ln-c">
                <span className="ln-section-title">{row.text}</span>
                {row.meta ? <span className="ln-section-meta">{row.meta}</span> : null}
              </span>
            </div>
          );
        }
        if (row.kind === "node") {
          return (
            <div key={`nd-${i}`} className="ln-row ln-node" role="listitem">
              <span className="ln-n" aria-hidden>
                {lineNo}
              </span>
              <span className="ln-c">{row.node}</span>
            </div>
          );
        }
        const clickable = Boolean(row.onClick);
        return (
          <div
            key={`tx-${i}`}
            className={`ln-row ln-text${clickable ? " ln-clickable" : ""}`}
            role="listitem"
            onClick={row.onClick}
            onKeyDown={
              clickable
                ? (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      row.onClick?.();
                    }
                  }
                : undefined
            }
            tabIndex={clickable ? 0 : undefined}
          >
            <span className="ln-n" aria-hidden>
              {lineNo}
            </span>
            <span className="ln-c">{row.text}</span>
          </div>
        );
      })}
    </div>
  );
}

export function circledIndex(index: number): string {
  return CIRCLED_NUMBERS[index] ?? `${index + 1}.`;
}

/** Split body text into display lines; keep blank lines as empty text rows. */
export function textToLineRows(text: string): Extract<LineDocRow, { kind: "text" }>[] {
  const normalized = text.replace(/\r\n/g, "\n").trimEnd();
  if (!normalized.trim()) return [];
  return normalized.split("\n").map((line) => ({
    kind: "text" as const,
    text: line.trim() || line,
  }));
}
