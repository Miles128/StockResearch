import { useMemo } from "react";
import type { CenterTab } from "../layoutTypes";

export interface ChatExample {
  label: string;
  query: string;
}

/** Per-tab chat example chips; kept out of App to avoid rebuilding the map on every render. */
export function useChatExamples(
  t: (key: string) => string,
  locale: string,
  centerTab: CenterTab,
): ChatExample[] {
  return useMemo(() => {
    const all = {
      market: {
        label: t("chat.exampleMarketLabel"),
        query: t("chat.exampleMarketQuery"),
      },
      stock: {
        label: t("chat.exampleStockLabel"),
        query: t("chat.exampleStockQuery"),
      },
      news: {
        label: t("chat.exampleNewsLabel"),
        query: t("chat.exampleNewsQuery"),
      },
      risk: {
        label: t("chat.exampleRiskLabel"),
        query: t("chat.exampleRiskQuery"),
      },
      sentiment: {
        label: t("chat.exampleSentimentLabel"),
        query: t("chat.exampleSentimentQuery"),
      },
      sector: {
        label: t("chat.exampleSectorLabel"),
        query: t("chat.exampleSectorQuery"),
      },
      pnl: {
        label: t("chat.examplePnlLabel"),
        query: t("chat.examplePnlQuery"),
      },
      topMover: {
        label: t("chat.exampleTopMoverLabel"),
        query: t("chat.exampleTopMoverQuery"),
      },
      newsImpact: {
        label: t("chat.exampleNewsImpactLabel"),
        query: t("chat.exampleNewsImpactQuery"),
      },
      topRisk: {
        label: t("chat.exampleTopRiskLabel"),
        query: t("chat.exampleTopRiskQuery"),
      },
      stress: {
        label: t("chat.exampleStressLabel"),
        query: t("chat.exampleStressQuery"),
      },
    };
    const byTab: Record<CenterTab, (typeof all)[keyof typeof all][]> = {
      focus: [all.stock, all.pnl, all.topMover, all.risk],
      market: [all.market, all.sentiment, all.sector, all.news],
      risk: [all.risk, all.topRisk, all.stress, all.pnl],
      news: [all.news, all.newsImpact, all.sentiment, all.market],
    };
    return byTab[centerTab];
    // locale 变化时 t 会一并更新，无需单独依赖 locale
  }, [t, centerTab]);
}
