import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PortfolioOptimizeBlock } from "../PortfolioOptimizeBlock";
import { api, type PortfolioOptimizeResult } from "../api";
import { I18nProvider } from "../i18n";

vi.mock("../api", () => ({
  api: {
    portfolioOptimize: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

function renderBlock() {
  return render(
    <I18nProvider>
      <PortfolioOptimizeBlock trigger="2:0" />
    </I18nProvider>,
  );
}

function makeResult(method: string): PortfolioOptimizeResult {
  return {
    method: method as PortfolioOptimizeResult["method"],
    method_label: method,
    rows: [
      {
        symbol: "600519",
        name: "贵州茅台",
        current_weight: 0.7,
        optimal_weight: 0.4,
      },
      {
        symbol: "000858",
        name: "五粮液",
        current_weight: 0.3,
        optimal_weight: 0.4,
      },
    ],
    cash_weight: 0.2,
    current_vol: 30.0,
    current_return: 8.0,
    optimal_vol: 20.0,
    optimal_return: 7.0,
    explanation: "教育参考解释",
    partial: false,
    notes: [],
    disclaimer: "组合优化为教育参考，不构成投资建议。",
    as_of: "2026-01-01",
  };
}

describe("PortfolioOptimizeBlock", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("loads min_vol on mount and renders weights after expand", async () => {
    mockedApi.portfolioOptimize.mockResolvedValue(makeResult("min_vol"));
    renderBlock();
    await waitFor(() => {
      expect(mockedApi.portfolioOptimize).toHaveBeenCalledWith("min_vol");
    });
    const title = await screen.findByText("组合优化参考");
    fireEvent.click(title);
    expect(await screen.findByText(/600519 贵州茅台/)).toBeDefined();
    expect(screen.getAllByText("40.0%").length).toBeGreaterThan(0);
    expect(screen.getByText("现金")).toBeDefined();
  });

  it("switches method and refetches", async () => {
    mockedApi.portfolioOptimize.mockResolvedValue(makeResult("risk_parity"));
    renderBlock();
    await waitFor(() => {
      expect(mockedApi.portfolioOptimize).toHaveBeenCalledTimes(1);
    });
    const title = await screen.findByText("组合优化参考");
    fireEvent.click(title);
    const riskParityBtn = await screen.findByText("风险平价");
    fireEvent.click(riskParityBtn);
    await waitFor(() => {
      expect(mockedApi.portfolioOptimize).toHaveBeenLastCalledWith("risk_parity");
    });
  });

  it("shows error state when fetch fails", async () => {
    mockedApi.portfolioOptimize.mockRejectedValue(new Error("boom"));
    renderBlock();
    const title = await screen.findByText("组合优化参考");
    fireEvent.click(title);
    expect(await screen.findByText("优化暂时不可用，稍后再试")).toBeDefined();
  });
});
