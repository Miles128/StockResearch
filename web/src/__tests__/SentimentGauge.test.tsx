import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SentimentGauge } from "../SentimentGauge";

vi.mock("../api", () => ({
  api: {
    marketSentiment: vi.fn().mockResolvedValue({
      score: 65,
      label: "乐观",
      drivers: [{ label: "指数", value: "+1.5%", impact: "positive" }],
      source: "composite",
    }),
    sectorSentiment: vi.fn().mockResolvedValue(null),
    stockSentiment: vi.fn().mockResolvedValue(null),
  },
}));

vi.mock("../i18n", () => ({
  useI18n: () => ({ t: (k: string) => k, locale: "zh" }),
}));

describe("SentimentGauge", () => {
  it("renders market sentiment", async () => {
    render(<SentimentGauge variant="market" />);
    // 等待加载完成
    const score = await screen.findByText("65");
    expect(score).toBeTruthy();
  });
});
