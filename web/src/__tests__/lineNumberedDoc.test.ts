import { describe, expect, it } from "vitest";
import { FOUR_DIM_LINE_OUTLINE } from "../fourDimOutlineData";
import { circledIndex, textToLineRows } from "../lineNumberedDoc";

describe("line numbered four-dim outline", () => {
  it("matches Lazyweb Line Numbers mockup section copy", () => {
    expect(FOUR_DIM_LINE_OUTLINE.map((s) => s.title)).toEqual([
      "基本面",
      "技术面",
      "情绪面",
      "筹码面",
    ]);
    expect(FOUR_DIM_LINE_OUTLINE[1].lines[0]).toBe("当前股价趋势如何？");
    expect(FOUR_DIM_LINE_OUTLINE[3].lines[2]).toBe("大股东或机构有增减持吗？");
  });

  it("counts 19 rows including spacers like the mockup", () => {
    let count = 0;
    FOUR_DIM_LINE_OUTLINE.forEach((section, index) => {
      if (index > 0) count += 1; // spacer
      count += 1; // section header
      count += section.lines.length;
    });
    expect(count).toBe(19);
  });

  it("uses circled indices ①–④", () => {
    expect([0, 1, 2, 3].map(circledIndex)).toEqual(["①", "②", "③", "④"]);
  });

  it("splits body text into numbered lines", () => {
    expect(textToLineRows("a\nb\n\nc").map((r) => r.text)).toEqual(["a", "b", "", "c"]);
  });
});
