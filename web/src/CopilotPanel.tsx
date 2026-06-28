import type { ReactNode } from "react";
import type { CopilotContext } from "./appTypes";
import type { CopilotThread } from "./copilotThreads";
import { CopilotThreadList } from "./CopilotThreadList";
import { useI18n } from "./i18n";
import { IconPanelBottom, IconPanelSide } from "./ui/Icons";

export type CopilotLayout = "horizontal" | "vertical";

interface CopilotPanelProps {
  open: boolean;
  threadTitle: string;
  threads: CopilotThread[];
  activeThreadId: string;
  userContext: CopilotContext | null;
  layout: CopilotLayout;
  children: ReactNode;
  onClose: () => void;
  onNewThread: () => void;
  onSelectThread: (id: string) => void;
  onRenameThread: (id: string, title: string) => void;
  onDeleteThread: (id: string) => void;
  onRemoveContext: () => void;
  onToggleLayout: () => void;
  onResizeStart: (axis: "x" | "y") => void;
}

export function CopilotPanel({
  open,
  threadTitle,
  threads,
  activeThreadId,
  userContext: _userContext,
  layout,
  children,
  onClose,
  onNewThread,
  onSelectThread,
  onRenameThread,
  onDeleteThread,
  onRemoveContext: _onRemoveContext,
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
      <CopilotThreadList
        threads={threads}
        activeId={activeThreadId}
        onSelect={onSelectThread}
        onNew={onNewThread}
        onRename={onRenameThread}
        onDelete={onDeleteThread}
      />
      <div className="copilot-panel-main">
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
              {layout === "horizontal" ? <IconPanelBottom /> : <IconPanelSide />}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onNewThread}>
              {t("chat.newThread")}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
              ×
            </button>
          </div>
        </div>
        <div className="copilot-content">{children}</div>
      </div>
    </aside>
  );
}
