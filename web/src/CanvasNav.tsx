import type { Tab } from "./appTypes";

interface CanvasNavProps {
  tab: Tab;
  items: { key: Tab; label: string }[];
  copilotOpen: boolean;
  copilotLabel: string;
  onTab: (tab: Tab) => void;
  onCopilot: () => void;
}

export function CanvasNav({
  tab,
  items,
  copilotOpen,
  copilotLabel,
  onTab,
  onCopilot,
}: CanvasNavProps) {
  return (
    <nav className="canvas-nav" aria-label="Canvas views">
      <div className="canvas-nav-primary">
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`canvas-nav-btn${tab === item.key ? " active" : ""}`}
            onClick={() => onTab(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="canvas-nav-tools">
        <button
          type="button"
          className={`canvas-tool-btn copilot-trigger${copilotOpen ? " active" : ""}`}
          onClick={onCopilot}
        >
          AI · {copilotLabel}
        </button>
      </div>
    </nav>
  );
}
