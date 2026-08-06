import { useState, type ReactNode } from "react";
import type { CopilotContext } from "./appTypes";
import type { CopilotThread } from "./copilotThreads";
import { CopilotThreadList } from "./CopilotThreadList";
import { useI18n } from "./i18n";
import { IconMessages, IconPlus } from "./ui/Icons";

interface CopilotPanelProps {
  open: boolean;
  threads: CopilotThread[];
  activeThreadId: string;
  userContext: CopilotContext | null;
  children: ReactNode;
  onCollapsePanel: () => void;
  onNewThread: () => void;
  onSelectThread: (id: string) => void;
  onDeleteThread: (id: string) => void;
  onResizeStart: () => void;
}

export function CopilotPanel({
  open,
  threads,
  activeThreadId,
  userContext: _userContext,
  children,
  onCollapsePanel,
  onNewThread,
  onSelectThread,
  onDeleteThread,
  onResizeStart,
}: CopilotPanelProps) {
  const { t } = useI18n();
  const [threadsOpen, setThreadsOpen] = useState(false);
  if (!open) return null;

  return (
    <aside className="copilot-panel layout-horizontal">
      <div className="copilot-panel-main">
        <div
          className="copilot-resize-handle col-axis"
          onMouseDown={(e) => {
            e.preventDefault();
            onResizeStart();
          }}
          role="separator"
          aria-orientation="vertical"
        />
        <CopilotThreadList
          open={threadsOpen}
          threads={threads}
          activeId={activeThreadId}
          onClose={() => setThreadsOpen(false)}
          onSelect={onSelectThread}
          onDelete={onDeleteThread}
        />
        {!threadsOpen && (
          <>
            <div className="copilot-toolbar">
              <button
                type="button"
                className="rail-toggle copilot-panel-collapse"
                onClick={onCollapsePanel}
                title={t("copilot.collapse")}
              >
                »
              </button>
              <div className="copilot-toolbar-actions">
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setThreadsOpen(true)}
                  title={t("copilot.threadList")}
                  aria-label={t("copilot.threadList")}
                >
                  <IconMessages />
                </button>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={onNewThread}
                  title={t("chat.newThread")}
                  aria-label={t("chat.newThread")}
                >
                  <IconPlus />
                </button>
              </div>
            </div>
            <div className="copilot-content">{children}</div>
          </>
        )}
      </div>
    </aside>
  );
}
