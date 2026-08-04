import type { AgentStreamEvent, RouteChoiceCardData, RouteChoiceOption } from "./api";
import type { TParams } from "./i18n";
import { localizeAgentDisplay, localizePositionAction, localizeVoteLabel } from "./uiLabels";

type TFn = (key: string, params?: TParams) => string;

const DIMENSION_START_KEYS = new Set([
  "status.research.start",
  "status.market.research.start",
  "status.industry.start",
]);

const INDUSTRY_START_KEYS = new Set(["status.industry.start"]);
const MARKET_START_KEYS = new Set(["status.market.research.start"]);

const SKIP_LOG_KEYS = new Set([
  "status.understanding",
  "status.react.thinking",
  "status.react.reply",
  "status.react.tool",
  "status.react.market_data",
  "status.react.stock_quote",
  "status.react.news",
  "status.react.skill",
  "status.research.start",
  "status.market.research.start",
  "status.industry.start",
  "status.research.news_factor",
  "status.market.research.news_factor",
  "status.research.summarize",
  "status.market.research.summarize",
  "status.research.battle_start",
  "status.market.research.battle_start",
  "status.industry.battle_start",
  "status.risk.analysis",
  "status.risk.manager",
  "status.risk.judge",
]);

export function statusEventKey(event: AgentStreamEvent): string | null {
  if (event.message_key) return event.message_key;
  return null;
}

export function translateStatusEvent(event: AgentStreamEvent, t: TFn): string {
  const key = event.message_key;
  if (!key) return event.message ?? "";
  if (key === "status.route") {
    const params = event.message_params ?? {};
    return t("stream.status.route", {
      debate: params.debate === "on" ? t("stream.debate.on") : t("stream.debate.off"),
      mode: t(`stream.routeMode.${String(params.mode ?? "")}`),
    });
  }
  return t(`stream.${key}`, (event.message_params ?? {}) as TParams);
}

export function shouldSeedDimensions(event: AgentStreamEvent): boolean {
  const key = statusEventKey(event);
  if (key && DIMENSION_START_KEYS.has(key)) return true;
  const msg = event.message ?? "";
  return (
    msg.includes("四维") || msg.includes("五维") || (msg.includes("板块") && msg.includes("维"))
  );
}

export function detectDimensionKind(
  event: AgentStreamEvent,
  statusText: string,
): "stock" | "market" | "industry" {
  const key = statusEventKey(event);
  if (key && INDUSTRY_START_KEYS.has(key)) return "industry";
  if (key && MARKET_START_KEYS.has(key)) return "market";
  if (statusText.includes("五维") || (statusText.includes("板块") && statusText.includes("维"))) {
    return "industry";
  }
  if (statusText.includes("市场") && statusText.includes("四维")) return "market";
  return "stock";
}

export function shouldSkipStatusLog(event: AgentStreamEvent): boolean {
  const key = statusEventKey(event);
  if (key && SKIP_LOG_KEYS.has(key)) return true;
  const msg = event.message ?? "";
  return (
    msg.includes("四维") ||
    msg.includes("五维") ||
    msg.includes("作战情") ||
    msg.includes("文本因子") ||
    msg.includes("Battle")
  );
}

export function localizeAgentName(agentId: string, fallback: string, t: TFn): string {
  return localizeAgentDisplay(agentId, fallback, t);
}

export function translateRouteReason(data: RouteChoiceCardData, t: TFn): string {
  const key = data.reason_key;
  if (key) {
    const translated = t(`stream.${key}`, (data.reason_params ?? {}) as TParams);
    if (translated !== `stream.${key}`) return translated;
  }
  return data.message ?? "";
}

export function normalizeStreamEvent(event: AgentStreamEvent, t: TFn): AgentStreamEvent {
  if (event.type === "status" && (event.message_key || event.message)) {
    return { ...event, message: translateStatusEvent(event, t) };
  }
  if (
    (event.type === "agent_start" || event.type === "dimension_ready") &&
    event.agent_id &&
    event.agent_name
  ) {
    return {
      ...event,
      agent_name: localizeAgentName(event.agent_id, event.agent_name, t),
    };
  }
  if (event.type === "vote" && event.agent_name) {
    const name = localizeAgentName(event.agent_id ?? "", event.agent_name, t);
    const vote = event.vote ? localizeVoteLabel(String(event.vote), t) : event.vote;
    return { ...event, agent_name: name, vote };
  }
  if (event.type === "vote_tally" && event.leading) {
    return {
      ...event,
      leading: localizeVoteLabel(String(event.leading), t),
    };
  }
  if (event.type === "judge") {
    const next: AgentStreamEvent = { ...event };
    if (event.position_action) {
      next.position_action = localizePositionAction(String(event.position_action), t);
    }
    if (event.holding_actions && Array.isArray(event.holding_actions)) {
      next.holding_actions = event.holding_actions.map((ha) => ({
        ...ha,
        action: localizePositionAction(String(ha.action), t),
      }));
    }
    return next;
  }
  return event;
}

export function translateRouteOption(
  opt: RouteChoiceOption,
  t: TFn,
): {
  label: string;
  description: string;
} {
  const labelParams = (opt.label_params ?? {}) as TParams;
  const descParams = (opt.description_params ?? {}) as TParams;
  if (opt.label_key) {
    const mode = String(labelParams.mode ?? "");
    if (mode) labelParams.mode = t(`stream.routeMode.${mode}`);
    const label = t(`stream.${opt.label_key}`, labelParams);
    const description = opt.description_key
      ? t(`stream.${opt.description_key}`, descParams)
      : (opt.description ?? "");
    return { label, description };
  }
  return { label: opt.label ?? "", description: opt.description ?? "" };
}
