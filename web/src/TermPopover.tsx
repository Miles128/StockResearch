import { useState, useRef, useEffect, type ReactNode } from "react";
import { useI18n } from "./i18n";

interface TermInfo {
  id: string;
  short: string;
  en: string;
  def: string;
  analogy: string;
}

interface TermPopoverProps {
  term: TermInfo;
  children: ReactNode;
}

export function TermPopover({ term, children }: TermPopoverProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const { t } = useI18n();

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <span
      ref={ref}
      className="term-inline"
      onClick={() => setOpen((v) => !v)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setOpen((v) => !v); }}
    >
      {children}
      {open && (
        <span className="term-popover" role="tooltip">
          <span className="term-popover-title">
            {term.short}
            {term.en && <span className="term-popover-en">{term.en}</span>}
          </span>
          <span className="term-popover-def">{term.def}</span>
          {term.analogy && (
            <span className="term-popover-analogy">
              💡 {t("term.analogyLabel")}：{term.analogy}
            </span>
          )}
        </span>
      )}
    </span>
  );
}

/** Render text containing <term data-id="...">...</term> markup into React elements.
 *  Only used in professional reading mode.
 */
export function renderTermMarkup(
  html: string,
  glossary: Record<string, TermInfo>,
): ReactNode[] {
  const parts: ReactNode[] = [];
  const regex = /<term data-id="([^"]+)">(.*?)<\/term>/g;
  let lastIdx = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = regex.exec(html)) !== null) {
    if (match.index > lastIdx) {
      parts.push(<span key={key++}>{html.slice(lastIdx, match.index)}</span>);
    }
    const termId = match[1];
    const termText = match[2];
    const termInfo = glossary[termId] || {
      id: termId,
      short: termId,
      en: "",
      def: t_ref("term.aiGenerated"),
      analogy: "",
    };
    parts.push(
      <TermPopover key={key++} term={termInfo}>
        {termText}
      </TermPopover>,
    );
    lastIdx = regex.lastIndex;
  }
  if (lastIdx < html.length) {
    parts.push(<span key={key}>{html.slice(lastIdx)}</span>);
  }
  return parts;
}

// Simple i18n accessor to avoid hook in non-component context
let _t: ((key: string) => string) | null = null;
function t_ref(key: string): string {
  return _t?.(key) ?? key;
}

// Hook to set the t function for renderTermMarkup
export function useTermRenderer() {
  const { t } = useI18n();
  useEffect(() => {
    _t = t;
  }, [t]);
}
