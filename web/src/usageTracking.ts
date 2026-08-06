/**
 * 本地使用统计（埋点）——仅用于"砍/留功能"决策。
 * 计数存 localStorage，不联网上报、不上传任何数据。
 */

export const EVENT_KEYS = {
  briefingView: "briefing_view",
  briefingGenerate: "briefing_generate",
  verifyRun: "verify_run",
  exportReport: "export_report",
  debateExpand: "debate_expand",
  termPopover: "term_popover",
  batchResearch: "batch_research",
  timelineView: "timeline_view",
  factorScreen: "factor_screen",
  alertsView: "alerts_view",
  plainToggle: "plain_toggle",
  watchlistAdd: "watchlist_add",
  priceAlertSet: "price_alert_set",
} as const;

export type UsageEventKey = (typeof EVENT_KEYS)[keyof typeof EVENT_KEYS];

const STORAGE_KEY = "stockresearch.usage.events";

export interface UsageEventStat {
  key: string;
  count: number;
}

function loadRaw(): Record<string, number> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, number>;
    return typeof parsed === "object" && parsed !== null ? parsed : {};
  } catch {
    return {};
  }
}

/** 记录一次功能使用。幂等、容错（storage 不可用则静默）。 */
export function recordEvent(key: UsageEventKey): void {
  try {
    const events = loadRaw();
    events[key] = (events[key] ?? 0) + 1;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(events));
  } catch {
    /* storage full/disabled — stats are best-effort */
  }
}

/** 按使用次数降序返回全部事件。 */
export function getUsageEvents(): UsageEventStat[] {
  const events = loadRaw();
  return Object.entries(events)
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => b.count - a.count);
}

export function clearUsageEvents(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
