import { useMemo, useState } from "react";
import { useI18n } from "../i18n";
import { EVENT_KEYS, clearUsageEvents, getUsageEvents } from "../usageTracking";

const EVENT_LABEL_KEYS: Record<string, string> = {
  [EVENT_KEYS.briefingView]: "usageEvents.evBriefingView",
  [EVENT_KEYS.briefingGenerate]: "usageEvents.evBriefingGenerate",
  [EVENT_KEYS.verifyRun]: "usageEvents.evVerifyRun",
  [EVENT_KEYS.exportReport]: "usageEvents.evExport",
  [EVENT_KEYS.debateExpand]: "usageEvents.evDebate",
  [EVENT_KEYS.termPopover]: "usageEvents.evTerm",
  [EVENT_KEYS.batchResearch]: "usageEvents.evBatch",
  [EVENT_KEYS.timelineView]: "usageEvents.evTimeline",
  [EVENT_KEYS.factorScreen]: "usageEvents.evFactorScreen",
  [EVENT_KEYS.alertsView]: "usageEvents.evAlerts",
  [EVENT_KEYS.plainToggle]: "usageEvents.evPlain",
  [EVENT_KEYS.watchlistAdd]: "usageEvents.evWatchlist",
  [EVENT_KEYS.priceAlertSet]: "usageEvents.evAlertSet",
};

/** 设置页「功能使用统计」块：本机计数，驱动砍/留决策。 */
export function UsageEventsBlock() {
  const { t } = useI18n();
  const [version, setVersion] = useState(0);
  const events = useMemo(() => getUsageEvents(), [version]);

  return (
    <section className="settings-section">
      <h4 className="settings-section-title">{t("settings.usageEventsTitle")}</h4>
      <p className="settings-hint">{t("settings.usageEventsHint")}</p>
      {events.length === 0 ? (
        <p className="settings-muted">{t("settings.usageEventsEmpty")}</p>
      ) : (
        <ul className="usage-events-list">
          {events.map((e) => (
            <li key={e.key} className="usage-event-row">
              <span className="usage-event-label">
                {t(EVENT_LABEL_KEYS[e.key] ?? "usageEvents.evUnknown")}
              </span>
              <span className="usage-event-count">{e.count}</span>
            </li>
          ))}
        </ul>
      )}
      <button
        type="button"
        className="settings-ghost-btn"
        onClick={() => {
          clearUsageEvents();
          setVersion((v) => v + 1);
        }}
      >
        {t("settings.usageEventsReset")}
      </button>
    </section>
  );
}
