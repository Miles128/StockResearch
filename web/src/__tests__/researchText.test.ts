import { describe, expect, it } from "vitest";
import { normalizeResearchConclusion } from "../researchText";

describe("normalizeResearchConclusion", () => {
  it("returns text already within 120-180 chars unchanged", () => {
    const text =
      "综合偏多，估值合理，基本面与情绪面共振，筹码结构相对稳定。".repeat(5);
    expect(text.length).toBeGreaterThanOrEqual(120);
    expect(text.length).toBeLessThanOrEqual(180);
    expect(normalizeResearchConclusion(text)).toBe(text);
  });

  it("compresses long text to at most 180 chars", () => {
    const long = "结论。".repeat(80);
    const normalized = normalizeResearchConclusion(long);
    expect(normalized.length).toBeLessThanOrEqual(180);
  });

  it("expands short text with dimension hints toward 120 chars", () => {
    const short = "贵州茅台(600519) 加权综合 7.2/10，倾向偏多。";
    const hints = [
      "基本面盈利质量持续改善，营收与利润增速位于行业中上水平，估值分位处于近五年中枢附近。",
      "情绪面新闻与政策口径偏暖，北向与两融资金小幅净流入，市场风险偏好有所回升。",
      "技术面短期均线呈多头排列，但成交量仍未有效放大，需观察后续放量确认。",
    ];
    const normalized = normalizeResearchConclusion(short, {
      expandHints: hints,
    });
    expect(normalized.length).toBeGreaterThanOrEqual(120);
    expect(normalized.length).toBeLessThanOrEqual(180);
    expect(normalized.startsWith("贵州茅台")).toBe(true);
  });

  it("prefers sentence boundary when compressing", () => {
    const text = `${"第一段结论。".repeat(8)}最后一句。`;
    const normalized = normalizeResearchConclusion(text, {
      minLen: 0,
      maxLen: 40,
    });
    expect(normalized.endsWith("。")).toBe(true);
    expect(normalized.length).toBeLessThanOrEqual(40);
  });
});
