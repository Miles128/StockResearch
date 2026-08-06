import { memo, type ReactNode } from "react";
import type { HoldingEnriched } from "../api";
import type { StreamState } from "../streamEvents";
import type { CopilotContext, Message } from "../appTypes";
import type { CopilotThread } from "../copilotThreads";
import type { AppMode } from "../modeSettings";
import { ChatPanel } from "../ChatPanel";
import { CopilotPanel } from "../CopilotPanel";

export interface CopilotColumnProps {
  open: boolean;
  threads: CopilotThread[];
  activeThreadId: string;
  messages: Message[];
  chatStream: StreamState;
  input: string;
  chatLoading: boolean;
  statusMsg: string;
  chatExamples: { label: string; query: string }[];
  holdings: HoldingEnriched[];
  appMode: AppMode;
  pageContext: CopilotContext | null;
  banner?: ReactNode;
  onCollapsePanel: () => void;
  onNewThread: () => void;
  onSelectThread: (id: string) => void;
  onDeleteThread: (id: string) => void;
  onResizeStart: () => void;
  onInputChange: (value: string) => void;
  onStartQuery: (query: string) => void;
  onSend: () => void;
  onAnalyzeHolding: (h: HoldingEnriched) => void;
  onConfirmStock: (originalMessage: string, symbol: string, name: string) => void;
}

/**
 * Isolated copilot column. Memoized so unrelated App state churn (holdings
 * polls, market/news refreshes, settings toggles) does not re-render the chat
 * tree; only chat-owned props (messages/chatStream/threads/input) trigger it.
 */
export const CopilotColumn = memo(function CopilotColumn({
  open,
  threads,
  activeThreadId,
  messages,
  chatStream,
  input,
  chatLoading,
  statusMsg,
  chatExamples,
  holdings,
  appMode,
  pageContext,
  banner,
  onCollapsePanel,
  onNewThread,
  onSelectThread,
  onDeleteThread,
  onResizeStart,
  onInputChange,
  onStartQuery,
  onSend,
  onAnalyzeHolding,
  onConfirmStock,
}: CopilotColumnProps) {
  if (!open) return null;
  return (
    <aside className="copilot-column">
      <CopilotPanel
        open
        threads={threads}
        activeThreadId={activeThreadId}
        userContext={pageContext}
        onCollapsePanel={onCollapsePanel}
        onNewThread={onNewThread}
        onSelectThread={onSelectThread}
        onDeleteThread={onDeleteThread}
        onResizeStart={onResizeStart}
      >
        {banner}
        <ChatPanel
          messages={messages}
          loading={chatLoading}
          statusMsg={statusMsg}
          chatStream={chatStream}
          input={input}
          onInputChange={onInputChange}
          chatExamples={chatExamples}
          holdings={holdings}
          appMode={appMode}
          onStartQuery={onStartQuery}
          onSend={onSend}
          onAnalyzeHolding={onAnalyzeHolding}
          onConfirmStock={onConfirmStock}
        />
      </CopilotPanel>
    </aside>
  );
});
