import type { ChatResponse } from "./api";
import { stripDisclaimer } from "./disclaimerText";
import { findResearchReport } from "./researchReportView";

/** 有 research 卡片时由 LightResearchCard 展示，不再重复渲染 reply 气泡。 */
export function shouldHideReplyBubble(cards?: ChatResponse["cards"]): boolean {
  return findResearchReport(cards) != null;
}

/** 过滤与最终 reply 重复的 text 卡片（单步 ReAct 常见重复来源）。 */
export function cardsWithoutReplyDuplicate(
  cards: ChatResponse["cards"] | undefined,
  replyContent: string,
): ChatResponse["cards"] {
  if (!cards?.length) return [];
  const reply = stripDisclaimer(replyContent).trim();
  if (!reply) return cards;
  return cards.filter((card) => {
    if (card.type !== "text" || !card.data || !("content" in card.data))
      return true;
    const text = String(
      (card.data as { content: string }).content || "",
    ).trim();
    if (!text) return false;
    if (text === reply || reply.includes(text)) return false;
    return true;
  });
}
