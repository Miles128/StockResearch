import { describe, expect, it } from "vitest";
import {
  buildKnownSymbols,
  syncFocusTabsFromChat,
  type KnownSymbol,
} from "../copilotFocusSync";
import type { ChatResponse } from "../api";

function emptyResponse(): ChatResponse {
  return {
    session_id: "s1",
    reply: "ok",
    cards: [],
    intent: "chat",
    follow_up_questions: [],
    disclaimer: "test",
  };
}

describe("syncFocusTabsFromChat", () => {
  const known: KnownSymbol[] = [
    { symbol: "600519", name: "贵州茅台" },
    { symbol: "300750", name: "宁德时代" },
  ];

  it("opens tab from research card", () => {
    const resp: ChatResponse = {
      ...emptyResponse(),
      cards: [
        {
          type: "research",
          data: { symbol: "600519", name: "贵州茅台" },
        },
      ],
    };
    const result = syncFocusTabsFromChat("分析茅台", resp, [], null, known);
    expect(result.activeId).toBe("stock:600519");
    expect(result.tabs).toHaveLength(1);
  });

  it("opens tab from query name when no research card", () => {
    const result = syncFocusTabsFromChat(
      "分析一下贵州茅台",
      emptyResponse(),
      [],
      null,
      known,
    );
    expect(result.activeId).toBe("stock:600519");
  });

  it("compare keeps both tabs", () => {
    const active = {
      kind: "stock" as const,
      symbol: "300750",
      name: "宁德时代",
    };
    const resp: ChatResponse = {
      ...emptyResponse(),
      cards: [
        { type: "research", data: { symbol: "600519", name: "贵州茅台" } },
      ],
    };
    const result = syncFocusTabsFromChat(
      "茅台和宁德时代对比",
      resp,
      [],
      active,
      known,
    );
    expect(result.tabs).toHaveLength(2);
    expect(result.activeId).toBe("stock:600519");
  });

  it("buildKnownSymbols dedupes holdings and watchlist", () => {
    const list = buildKnownSymbols(
      [{ symbol: "600519", name: "贵州茅台" }],
      [
        { symbol: "600519", name: "贵州茅台" },
        { symbol: "000001", name: "平安银行" },
      ],
    );
    expect(list).toHaveLength(2);
  });
});
