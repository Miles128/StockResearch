import type { Briefing } from "./api";
import type { TParams } from "./i18n";

type TFn = (key: string, params?: TParams) => string;

const AGENT_ZH_TO_KEY: Record<string, string> = {
  基本面: "fundamental",
  技术面: "technical",
  情绪面: "sentiment",
  筹码面: "chips",
  宏观面: "macro",
  行业面: "industry",
  政策舆情: "policy",
  资金流向: "capital",
  估值景气: "valuation",
  结构持仓: "structure",
  规则引擎: "rules",
  市场环境: "market_env",
  相关性: "correlation",
  情景推演: "scenario",
  裁判: "judge",
  风控: "risk_agent",
  新闻员: "news_reporter",
  财经快讯: "financial_news",
};

const BRIEFING_TITLE_ZH: Record<string, string> = {
  盘前简报: "briefing.title.premarket",
  盘中简报: "briefing.title.intraday",
  盘后简报: "briefing.title.postmarket",
  收盘简报: "briefing.title.postmarket",
};

const BRIEFING_SECTION_ZH: Record<string, string> = {
  市场概览: "briefing.section.market",
  大盘概况: "briefing.section.market",
  持仓快照: "briefing.section.holdings",
  持仓表现: "briefing.section.holdings",
  新闻文本因子: "briefing.section.newsFactor",
  新闻脉络: "briefing.section.newsFlow",
  风控提醒: "briefing.section.riskAlerts",
  综合结论: "briefing.section.conclusion",
};

const VOTE_ZH: Record<string, string> = {
  偏多: "card.bullish",
  偏空: "card.bearish",
  中性: "card.neutral",
  bullish: "card.bullish",
  bearish: "card.bearish",
  neutral: "card.neutral",
};

const POSITION_ACTION_ZH: Record<string, string> = {
  仓位偏高: "stream.actions.high",
  仓位偏低: "stream.actions.low",
  仓位适中: "stream.actions.neutral",
  建议控制仓位: "stream.actions.control",
  暂不调整: "stream.actions.noChange",
};

/** Stable CSS class suffix for position-bias styling (PRD §9.1). */
export function positionActionCssClass(action: string): string {
  const key = POSITION_ACTION_ZH[action.trim()];
  if (key === "stream.actions.high") return "reduce";
  if (key === "stream.actions.low") return "add";
  if (key === "stream.actions.noChange") return "hold_no_change";
  if (key === "stream.actions.control" || key === "stream.actions.neutral") return "hold";
  const localized = action.toLowerCase();
  if (localized.includes("overweight") || localized.includes("high")) return "reduce";
  if (localized.includes("underweight") || localized.includes("low")) return "add";
  if (localized.includes("no change")) return "hold_no_change";
  return "hold";
}

export function localizeAgentDisplay(agentId: string, fallback: string, t: TFn): string {
  const byId = t(`stream.agents.${agentId}`);
  if (byId !== `stream.agents.${agentId}`) return byId;

  if (fallback.startsWith("龙头·")) {
    return t("stream.agents.leader", { name: fallback.slice(3) });
  }
  if (fallback.endsWith("投票")) {
    const base = fallback.slice(0, -2);
    const name = localizeAgentDisplay("", base, t);
    return t("stream.voteSuffix", { name });
  }

  const key = AGENT_ZH_TO_KEY[fallback];
  if (key) {
    const translated = t(`stream.agents.${key}`);
    if (translated !== `stream.agents.${key}`) return translated;
  }
  return fallback;
}

export function localizeVoteLabel(vote: string, t: TFn): string {
  const i18nKey = VOTE_ZH[vote];
  return i18nKey ? t(i18nKey) : vote;
}

export function localizeSentiment(value: string, t: TFn): string {
  const key = `news.sentiment.${value}`;
  const translated = t(key);
  return translated !== key ? translated : value;
}

export function localizeImpactLevel(value: string, t: TFn): string {
  const key = `news.impact.${value}`;
  const translated = t(key);
  return translated !== key ? translated : value;
}

export function localizePositionAction(action: string, t: TFn): string {
  const i18nKey = POSITION_ACTION_ZH[action];
  return i18nKey ? t(i18nKey) : action;
}

export function localizeBriefing(briefing: Briefing, t: TFn): Briefing {
  const titleKey = BRIEFING_TITLE_ZH[briefing.title];
  return {
    ...briefing,
    title: titleKey ? t(titleKey) : briefing.title,
    sections: briefing.sections.map((s) => {
      const sectionKey = BRIEFING_SECTION_ZH[s.title];
      return {
        ...s,
        title: sectionKey ? t(sectionKey) : s.title,
      };
    }),
  };
}

export function formatBriefingMarkdown(briefing: Briefing): string {
  const lines = [`**${briefing.title}**`, "", briefing.summary.trim()];
  for (const section of briefing.sections) {
    lines.push("", `### ${section.title}`, "", section.content.trim());
  }
  return lines.join("\n");
}

export function localizeRiskRuleId(ruleId: string, t: TFn): string {
  const key = `risk.rules.${ruleId}`;
  const translated = t(key);
  return translated !== key ? translated : ruleId;
}

export function localizeSeverity(severity: string, t: TFn): string {
  const key = `risk.severity.${severity}`;
  const translated = t(key);
  return translated !== key ? translated : severity;
}

export function localizeRating(value: string, t: TFn): string {
  const key = `rating.${value}`;
  const translated = t(key);
  if (translated !== key) return translated;
  const zhMap: Record<string, string> = {
    优: "excellent",
    良: "good",
    中: "fair",
    差: "poor",
    高: "high",
    低: "low",
  };
  const mapped = zhMap[value];
  return mapped ? t(`rating.${mapped}`) : value;
}

/** Map research confidence high/medium/low (or 高/中/低) to locale label. */
export function localizeConfidence(value: string, t: TFn): string {
  const raw = value.trim();
  const normalized = raw.toLowerCase();
  const keyByValue: Record<string, string> = {
    high: "card.confidenceHigh",
    medium: "card.confidenceMedium",
    low: "card.confidenceLow",
    高: "card.confidenceHigh",
    中: "card.confidenceMedium",
    低: "card.confidenceLow",
  };
  const key = keyByValue[normalized] ?? keyByValue[raw];
  if (!key) return value;
  const translated = t(key);
  return translated !== key ? translated : value;
}
