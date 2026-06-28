import { useState } from "react";
import type { CopilotThread } from "./copilotThreads";
import { useI18n } from "./i18n";

interface CopilotThreadListProps {
  threads: CopilotThread[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
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
  threads,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: CopilotThreadListProps) {
  const { t, locale } = useI18n();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  function startRename(thread: CopilotThread) {
    setEditingId(thread.id);
    setDraft(thread.title);
  }

  function commitRename(id: string) {
    onRename(id, draft);
    setEditingId(null);
    setDraft("");
  }

  return (
    <aside className="copilot-thread-rail" aria-label={t("copilot.threadList")}>
      <div className="copilot-thread-rail-head">
        <span>{t("copilot.threadList")}</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onNew} title={t("chat.newThread")}>
          +
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
              {editingId === thread.id ? (
                <input
                  className="copilot-thread-rename"
                  value={draft}
                  autoFocus
                  onChange={(e) => setDraft(e.target.value)}
                  onBlur={() => commitRename(thread.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitRename(thread.id);
                    if (e.key === "Escape") setEditingId(null);
                  }}
                />
              ) : (
                <button
                  type="button"
                  className={`copilot-thread-item${active ? " active" : ""}`}
                  onClick={() => onSelect(thread.id)}
                  onDoubleClick={() => startRename(thread)}
                >
                  <span className="copilot-thread-title">{thread.title}</span>
                  <span className="copilot-thread-preview">{preview}</span>
                  <span className="copilot-thread-when">{formatWhen(thread.updatedAt, locale)}</span>
                </button>
              )}
              {active && editingId !== thread.id && (
                <div className="copilot-thread-actions">
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => startRename(thread)}>
                    {t("copilot.renameThread")}
                  </button>
                  {threads.length > 1 && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => onDelete(thread.id)}
                    >
                      {t("copilot.deleteThread")}
                    </button>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
