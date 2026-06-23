import type { ReactNode } from "react";
import type { CopilotContext } from "./appTypes";
import { useI18n } from "./i18n";

interface CopilotPanelProps {
  open: boolean;
  threadTitle: string;
  userContext: string;
  pageContext: CopilotContext | null;
  children: ReactNode;
  onClose: () => void;
  onNewThread: () => void;
  onRemoveContext: () => void;
}

export function CopilotPanel({
  open,
  threadTitle,
  userContext,
  pageContext,
  children,
  onClose,
  onNewThread,
  onRemoveContext,
}: CopilotPanelProps) {
  const { t } = useI18n();
  if (!open) return null;

  return (
    <aside className="copilot-panel">
      <div className="copilot-header">
        <div>
          <span className="copilot-eyebrow">AI · COPILOT</span>
          <strong>{threadTitle || t("chat.threadEmpty")}</strong>
        </div>
        <div className="copilot-header-actions">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onNewThread}>
            {t("chat.newThread")}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            ×
          </button>
        </div>
      </div>
      <div className="copilot-contexts">
        <div className="copilot-context-row">
          <span>{t("chat.userContext")}</span>
          <strong>{userContext}</strong>
        </div>
        <div className="copilot-context-row">
          <span>{t("chat.pageContext")}</span>
          {pageContext ? (
            <button type="button" className="context-chip active" onClick={onRemoveContext}>
              {pageContext.label} <span>×</span>
            </button>
          ) : (
            <span className="muted">{t("chat.noPageContext")}</span>
          )}
        </div>
        <p className="copilot-context-notice">{t("chat.contextNotice")}</p>
      </div>
      <div className="copilot-content">{children}</div>
    </aside>
  );
}
