import { useEffect, useState } from "react";
import { api, type DailyActionCenter, type ActionSignal } from "./api";
import { useI18n } from "./i18n";
import { SignalIcon } from "./ui/Icons";

interface ActionCenterProps {
  onNavigate: (tab: string) => void;
  onChatQuery: (query: string) => void;
}

export function ActionCenter({ onNavigate, onChatQuery }: ActionCenterProps) {
  const { t } = useI18n();
  const [data, setData] = useState<DailyActionCenter | null>(null);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    api
      .dailyActions()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  function renderHeader(summary?: string, extra?: React.ReactNode) {
    return (
      <div
        className="action-center-header card-header"
        onClick={() => setCollapsed((c) => !c)}
        role="button"
        tabIndex={0}
      >
        <span className="card-header-title">{t("actionCenter.title")}</span>
        <span className="action-center-header-right">
          {summary ? <span className="action-center-summary-inline">{summary}</span> : null}
          {extra}
          <span className={`action-center-chevron ${collapsed ? "collapsed" : ""}`}>▾</span>
        </span>
      </div>
    );
  }

  if (loading && !data) {
    return (
      <div className={`action-center${collapsed ? " collapsed" : ""}`}>
        {renderHeader(t("actionCenter.loading"))}
      </div>
    );
  }

  if (!data || data.signals.length === 0) {
    return (
      <div className={`action-center${collapsed ? " collapsed" : ""}`}>
        {renderHeader(data?.summary || t("actionCenter.empty"))}
      </div>
    );
  }

  function handleSignalClick(signal: ActionSignal) {
    if (signal.action_target === "risk") {
      onNavigate("risk");
    } else if (signal.action_target === "news") {
      onNavigate("news");
    } else if (signal.action_target === "market") {
      onNavigate("market");
    } else if (signal.action_target === "chat" && signal.symbol) {
      onChatQuery(`分析${signal.symbol}`);
    }
  }

  return (
    <div className={`action-center${collapsed ? " collapsed" : ""}`}>
      {renderHeader(
        data.summary,
        <span className="action-center-count">
          {t("actionCenter.signalCount", { n: String(data.signals.length) })}
        </span>,
      )}
      {!collapsed && (
        <div className="action-center-signals">
          {data.signals.map((signal, i) => (
            <div
              key={i}
              className={`action-signal-card action-signal-${signal.severity}`}
              onClick={() => handleSignalClick(signal)}
              role="button"
              tabIndex={0}
            >
              <div className="signal-card-header">
                <span className="signal-icon">
                  <SignalIcon type={signal.type} severity={signal.severity} />
                </span>
                <span className="signal-title">{signal.title}</span>
              </div>
              {signal.detail && <p className="signal-detail">{signal.detail}</p>}
              {signal.action && <span className="signal-action">{signal.action}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
