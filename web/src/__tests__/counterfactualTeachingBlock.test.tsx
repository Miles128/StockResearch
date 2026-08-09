import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CounterfactualTeachingBlock } from "../CounterfactualTeachingBlock";
import { api, type CounterfactualTeaching, type HoldingEnriched } from "../api";
import { I18nProvider } from "../i18n";

vi.mock("../api", () => ({
  api: {
    portfolioCounterfactual: vi.fn(),
    glossary: vi.fn().mockResolvedValue({ terms: [] }),
  },
}));

const mockedApi = vi.mocked(api);

function renderBlock(props: { holdings: HoldingEnriched[]; trigger: string }) {
  return render(
    <I18nProvider>
      <CounterfactualTeachingBlock {...props} />
    </I18nProvider>,
  );
}

function makeHolding(overrides: Partial<HoldingEnriched> = {}): HoldingEnriched {
  return {
    symbol: "600519",
    name: "贵州茅台",
    cost_price: 1800,
    quantity: 100,
    sector: "白酒",
    quote_available: true,
    price: 2000,
    change_pct: 1.0,
    price_label: "收盘",
    market_session: "closed",
    ...overrides,
  };
}

function makeTeaching(symbol: string): CounterfactualTeaching {
  return {
    symbol,
    name: symbol === "600519" ? "贵州茅台" : "Test",
    position_value: 180000,
    segments: [
      {
        concept: "drawdown",
        title: "回撤",
        story: "假设你买入 18.0 万元，账面最多浮亏 20%。",
        partial: false,
      },
      {
        concept: "volatility",
        title: "波动",
        story: "年化波动率约 23%。",
        partial: false,
      },
      {
        concept: "valuation",
        title: "估值",
        story: "PE 分位教学。",
        partial: false,
      },
    ],
    bars_adjust: "qfq",
    bars_source: "warehouse",
    notes: [],
    disclaimer: "情景教学用真实历史数据演示概念，非预测。",
    as_of: "2026-01-01",
  };
}

describe("CounterfactualTeachingBlock", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.glossary).mockResolvedValue([]);
  });

  it("returns null without holdings", () => {
    const { container } = renderBlock({ holdings: [], trigger: "0:0" });
    expect(container.innerHTML).toBe("");
  });

  it("fetches teaching for top holdings and renders segments", async () => {
    mockedApi.portfolioCounterfactual.mockResolvedValue({
      items: [makeTeaching("600519")],
    });
    renderBlock({ holdings: [makeHolding()], trigger: "1:0" });
    await waitFor(() => {
      expect(mockedApi.portfolioCounterfactual).toHaveBeenCalledWith(["600519"]);
    });
    const title = await screen.findByText("假设你当时……（情景教学）");
    expect(title).toBeDefined();
    // 折叠块默认收起，点击展开后才能看到教学段
    fireEvent.click(title);
    expect(await screen.findByText("回撤")).toBeDefined();
    expect(await screen.findByText("波动")).toBeDefined();
    expect(await screen.findByText("估值")).toBeDefined();
  });

  it("sends only top-N symbols by position value", async () => {
    mockedApi.portfolioCounterfactual.mockResolvedValue({ items: [] });
    const holdings = [
      makeHolding({ symbol: "000001", cost_price: 10, quantity: 1000 }),
      makeHolding({ symbol: "000002", cost_price: 100, quantity: 1000 }),
      makeHolding({ symbol: "000003", cost_price: 50, quantity: 1000 }),
      makeHolding({ symbol: "000004", cost_price: 200, quantity: 1000 }),
      makeHolding({ symbol: "000005", cost_price: 5, quantity: 1000 }),
    ];
    renderBlock({ holdings, trigger: "5:0" });
    await waitFor(() => {
      expect(mockedApi.portfolioCounterfactual).toHaveBeenCalledTimes(1);
    });
    const sent = mockedApi.portfolioCounterfactual.mock.calls[0][0];
    expect(sent).toHaveLength(4);
    expect(sent[0]).toBe("000004"); // 200k 最大
  });

  it("shows error state when fetch fails", async () => {
    mockedApi.portfolioCounterfactual.mockRejectedValue(new Error("boom"));
    renderBlock({ holdings: [makeHolding()], trigger: "1:0" });
    const title = await screen.findByText("假设你当时……（情景教学）");
    fireEvent.click(title);
    expect(await screen.findByText("情景教学暂时不可用，稍后再试")).toBeDefined();
  });
});
