import { useEffect, useState } from "react";
import { api, type DailyActionCenter, type ActionSignal } from "./api";
import { useI18n } from "./i18n";

interface ActionCenterProps {
  onNavigate: (tab: string) => void;
  onChatQuery: (query: string) => void;
}

function signalIcon(type: string, severity: string): string {
  if (type === "risk" && severity === "critical") return "⚠";
  if (type === "risk" && severity === "warning") return "⚡";
  if (type === "news") return "📰";
  if (type === "price") return "📊";
  return "📋";
}

export function ActionCenter({ onNavigate, onChatQuery }: ActionCenterProps) {
  const { t } = useI18n();
  const [data, setData] = useState<DailyActionCenter | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .dailyActions()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading && !data) {
    return (
      <div className="action-center">
        <div className="action-center-header">
          <span className="action-center-title">{t("actionCenter.title")}</span>
          <span className="action-center-loading">{t("actionCenter.loading")}</span>
        </div>
      </div>
    );
  }

  if (!data || data.signals.length === 0) {
    return (
      <div className="action-center">
        <div className="action-center-header">
          <span className="action-center-title">{t("actionCenter.title")}</span>
        </div>
        <div className="action-center-empty">{data?.summary || t("actionCenter.empty")}</div>
      </div>
    );
  }

  function handleSignalClick(signal: ActionSignal) {
    if (signal.action_target === "risk") {
      onNavigate("risk");
    } else if (signal.action_target === "news") {
      onNavigate("news");
    } else if (signal.action_target === "chat" && signal.symbol) {
      onChatQuery(`分析${signal.symbol}`);
    }
  }

  return (
    <div className="action-center">
      <div className="action-center-header">
        <span className="action-center-title">{t("actionCenter.title")}</span>
        <span className="action-center-count">
          {t("actionCenter.signalCount", { n: String(data.signals.length) })}
        </span>
      </div>
      <div className="action-center-signals">
        {data.signals.map((signal, i) => (
          <div
            key={i}
            className={`action-signal action-signal-${signal.severity}`}
            onClick={() => handleSignalClick(signal)}
            role="button"
            tabIndex={0}
          >
            <span className="signal-icon">{signalIcon(signal.type, signal.severity)}</span>
            <div className="signal-body">
              <span className="signal-title">{signal.title}</span>
              {signal.detail && <span className="signal-detail">{signal.detail}</span>}
            </div>
            {signal.action && (
              <span className="signal-action">{signal.action}</span>
            )}
          </div>
        ))}
      </div>
      <div className="action-center-summary">{data.summary}</div>
    </div>
  );
}
