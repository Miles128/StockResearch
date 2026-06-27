import type { Tab } from "./appTypes";

interface TabNavProps {
  className: string;
  tab: Tab;
  onTab: (key: Tab) => void;
  items: { key: Tab; label: string }[];
  ariaLabel: string;
  compact?: boolean;
  locale?: "zh" | "en";
  onLocaleToggle?: () => void;
}

export function TabNav({
  className,
  tab,
  onTab,
  items,
  ariaLabel,
  compact = false,
  locale,
  onLocaleToggle,
}: TabNavProps) {
  return (
    <nav className={className} aria-label={ariaLabel}>
      {items.map((n) => (
        <button
          key={n.key}
          type="button"
          className={`nav-btn${tab === n.key ? " active" : ""}`}
          onClick={() => onTab(n.key)}
        >
          <span className="nav-label">{n.label}</span>
        </button>
      ))}
      {onLocaleToggle && locale && (
        <button
          type="button"
          className="nav-btn nav-locale-btn"
          onClick={onLocaleToggle}
          title={locale === "zh" ? "English" : "中文"}
          aria-label={locale === "zh" ? "Switch to English" : "切换为中文"}
        >
          <span className="nav-label">{locale === "zh" ? "EN" : "中"}</span>
        </button>
      )}
    </nav>
  );
}
