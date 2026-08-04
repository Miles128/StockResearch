import type { FocusTab } from "./focusTabs";
import { focusTabLabel } from "./focusTabs";
import type { FocusContext } from "./layoutTypes";
import { useI18n } from "./i18n";
import { IconClose } from "./ui/Icons";

interface FocusTabBarProps {
  tabs: FocusTab[];
  activeId: string | null;
  onSelect: (tabId: string) => void;
  onClose: (tabId: string) => void;
}

function tabMono(context: FocusContext): string | null {
  if (context.kind === "stock") return context.symbol;
  if (context.kind === "index") return context.symbol;
  return null;
}

export function FocusTabBar({ tabs, activeId, onSelect, onClose }: FocusTabBarProps) {
  const { t } = useI18n();
  if (tabs.length === 0) return null;

  return (
    <div className="focus-tab-bar" role="tablist" aria-label={t("focus.tabsAria")}>
      {tabs.map((tab) => (
        <div
          key={tab.id}
          role="tab"
          aria-selected={tab.id === activeId}
          className={`focus-tab${tab.id === activeId ? " active" : ""}`}
        >
          <button type="button" className="focus-tab-label" onClick={() => onSelect(tab.id)}>
            <span>{focusTabLabel(tab.context)}</span>
            {tabMono(tab.context) && <span className="mono muted">{tabMono(tab.context)}</span>}
          </button>
          <button
            type="button"
            className="icon-btn focus-tab-close"
            onClick={() => onClose(tab.id)}
            title={t("stockDetail.close")}
            aria-label={t("stockDetail.close")}
          >
            <IconClose />
          </button>
        </div>
      ))}
    </div>
  );
}
