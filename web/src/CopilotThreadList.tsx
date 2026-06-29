import type { CopilotThread } from "./copilotThreads";
import { useI18n } from "./i18n";
import { IconClose } from "./ui/Icons";

interface CopilotThreadListProps {
  open: boolean;
  threads: CopilotThread[];
  activeId: string;
  onClose: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

function formatWhen(ts: number, locale: "zh" | "en"): string {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return locale === "zh" ? "刚刚" : "Just now";
  if (mins < 60) return locale === "zh" ? `${mins} 分钟前` : `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return locale === "zh" ? `${hours} 小时前` : `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return locale === "zh" ? `${days} 天前` : `${days}d ago`;
}

export function CopilotThreadList({
  open,
  threads,
  activeId,
  onClose,
  onSelect,
  onDelete,
}: CopilotThreadListProps) {
  const { t, locale } = useI18n();
  if (!open) return null;

  return (
    <div className="copilot-thread-overlay" aria-label={t("copilot.threadList")}>
      <div className="copilot-thread-overlay-head">
        <span className="flat-section-title">{t("copilot.threadList")}</span>
        <button type="button" className="icon-btn" onClick={onClose} title={t("stockDetail.close")}>
          <IconClose />
        </button>
      </div>
      <ul className="copilot-thread-list">
        {threads.map((thread) => {
          const active = thread.id === activeId;
          const preview =
            [...thread.messages].reverse().find((m) => m.role === "assistant")?.content ||
            [...thread.messages].reverse().find((m) => m.role === "user")?.content ||
            t("chat.threadEmpty");
          return (
            <li key={thread.id}>
              <button
                type="button"
                className={`copilot-thread-item${active ? " active" : ""}`}
                onClick={() => {
                  onSelect(thread.id);
                  onClose();
                }}
              >
                <span className="copilot-thread-title">{thread.title}</span>
                <span className="copilot-thread-preview">{preview}</span>
                <span className="copilot-thread-when">{formatWhen(thread.updatedAt, locale)}</span>
              </button>
              {threads.length > 1 && (
                <button
                  type="button"
                  className="copilot-thread-delete icon-btn"
                  onClick={() => onDelete(thread.id)}
                  title={t("copilot.deleteThread")}
                >
                  ×
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
