import { describe, expect, it } from "vitest";
import { cardsWithoutReplyDuplicate, shouldHideReplyBubble } from "../replyCardDedup";

describe("replyCardDedup", () => {
  it("hides reply when research card exists", () => {
    expect(
      shouldHideReplyBubble([
        {
          type: "research",
          data: {
            symbol: "600519",
            name: "茅台",
            composite_score: 8,
            summary: "摘要",
          },
        },
      ]),
    ).toBe(true);
  });

  it("filters text card duplicate of reply", () => {
    const cards = [
      { type: "text" as const, data: { content: "茅台现价 1680 元" } },
      {
        type: "financial" as const,
        data: { symbol: "600519", name: "茅台", ratios: [], summary: "" },
      },
    ];
    const filtered = cardsWithoutReplyDuplicate(cards, "茅台现价 1680 元，估值偏高。");
    expect(filtered).toHaveLength(1);
    expect(filtered[0]?.type).toBe("financial");
  });
});
