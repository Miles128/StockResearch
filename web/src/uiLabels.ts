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
  看多派: "bull_side",
  看空派: "bear_side",
  风控: "risk_agent",
  新闻员: "news_reporter",
  财经快讯: "financial_news",
};

const BRIEFING_TITLE_ZH: Record<string, string> = {
  盘前简报: "briefing.title.morning",
  收盘简报: "briefing.title.closing",
};

const BRIEFING_SECTION_ZH: Record<string, string> = {
  市场概览: "briefing.section.market",
  持仓快照: "briefing.section.holdings",
  新闻文本因子: "briefing.section.newsFactor",
  风控提醒: "briefing.section.riskAlerts",
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
  加仓: "stream.actions.add",
  减仓: "stream.actions.reduce",
  持有观望: "stream.actions.hold",
  观望: "stream.actions.hold",
};

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

export function localizeDebateAgentName(name: string, t: TFn): string {
  const key = AGENT_ZH_TO_KEY[name];
  if (key) {
    const label = t(`stream.agents.${key}`);
    if (label !== `stream.agents.${key}`) return `${label} ${t("card.analyst")}`;
  }
  return `${name} ${t("card.analyst")}`;
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
