import { useState, type ReactNode } from "react";

interface CollapsibleSectionProps {
  title: string;
  summary?: ReactNode;
  defaultCollapsed?: boolean;
  headerExtra?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function CollapsibleSection({
  title,
  summary,
  defaultCollapsed = false,
  headerExtra,
  children,
  className = "",
}: CollapsibleSectionProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <section className={`flat-section collapsible-section${collapsed ? " collapsed" : ""}${className ? ` ${className}` : ""}`}>
      <div className="collapsible-section-head">
        <button
          type="button"
          className="collapsible-section-toggle"
          onClick={() => setCollapsed((v) => !v)}
          aria-expanded={!collapsed}
        >
          <span className={`collapsible-chevron${collapsed ? " collapsed" : ""}`}>▾</span>
          <span className="flat-section-title">{title}</span>
          {summary ? <span className="collapsible-summary">{summary}</span> : null}
        </button>
        {headerExtra}
      </div>
      {!collapsed && <div className="collapsible-section-body">{children}</div>}
    </section>
  );
}
