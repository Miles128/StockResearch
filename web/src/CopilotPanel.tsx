import type { ReactNode } from "react";
import type { CopilotContext } from "./appTypes";
import { useI18n } from "./i18n";

export type CopilotLayout = "horizontal" | "vertical";

interface CopilotPanelProps {
  open: boolean;
  threadTitle: string;
  userContext: CopilotContext | null;
  layout: CopilotLayout;
  children: ReactNode;
  onClose: () => void;
  onNewThread: () => void;
  onRemoveContext: () => void;
  onToggleLayout: () => void;
  onResizeStart: (axis: "x" | "y") => void;
}

export function CopilotPanel({
  open,
  threadTitle,
  userContext,
  layout,
  children,
  onClose,
  onNewThread,
  onRemoveContext,
  onToggleLayout,
  onResizeStart,
}: CopilotPanelProps) {
  const { t } = useI18n();
  if (!open) return null;

  const axis = layout === "vertical" ? "y" : "x";
  const layoutToggleTitle =
    layout === "horizontal"
      ? t("copilot.switchToVertical")
      : t("copilot.switchToHorizontal");

  return (
    <aside className={`copilot-panel layout-${layout}`}>
      <div
        className={`copilot-resize-handle ${axis === "y" ? "row-axis" : "col-axis"}`}
        onMouseDown={(e) => {
          e.preventDefault();
          onResizeStart(axis);
        }}
        role="separator"
        aria-orientation={axis === "y" ? "horizontal" : "vertical"}
      />
      <div className="copilot-header">
        <div>
          <span className="copilot-eyebrow">{t("nav.copilot")}</span>
          <strong>{threadTitle || t("chat.threadEmpty")}</strong>
        </div>
        <div className="copilot-header-actions">
          <button
            type="button"
            className="btn btn-ghost btn-sm copilot-layout-toggle"
            onClick={onToggleLayout}
            title={layoutToggleTitle}
            aria-label={layoutToggleTitle}
          >
            {layout === "horizontal" ? "⤓" : "⤔"}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onNewThread}>
            {t("chat.newThread")}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            ×
          </button>
        </div>
      </div>
      {userContext ? (
        <div className="copilot-contexts">
          <div className="copilot-context-row">
            <span>{t("chat.userContext")}</span>
            <button type="button" className="context-chip active" onClick={onRemoveContext}>
              {userContext.label} <span>×</span>
            </button>
          </div>
          <p className="copilot-context-notice">{t("chat.contextNotice")}</p>
        </div>
      ) : null}
      <div className="copilot-content">{children}</div>
    </aside>
  );
}
