import { describe, it, expect } from "vitest";
import type { ComponentProps } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MarkdownContent } from "../MarkdownContent";
import { GlossaryProvider } from "../GlossaryContext";
import { I18nProvider } from "../i18n";
import type { GlossaryTerm } from "../api";

const sampleTerms: Record<string, GlossaryTerm> = {
  PE: {
    id: "PE",
    short: "市盈率",
    en: "Price-to-Earnings Ratio",
    def: "股价 ÷ 每股收益，衡量估值高低",
    analogy: "花多少钱买1元年利润",
  },
};

function renderMarkdown(
  text: string,
  props: Partial<ComponentProps<typeof MarkdownContent>> = {},
) {
  return render(
    <I18nProvider>
      <GlossaryProvider enabled terms={sampleTerms}>
        <MarkdownContent text={text} {...props} />
      </GlossaryProvider>
    </I18nProvider>,
  );
}

describe("MarkdownContent", () => {
  it("renders basic markdown text", () => {
    const { container } = renderMarkdown("hello world");
    expect(container.textContent).toContain("hello world");
  });

  it("renders bold and italic", () => {
    const { container } = renderMarkdown("this is **bold** text");
    expect(container.querySelector("strong")).not.toBeNull();
  });

  it("renders code blocks", () => {
    const { container } = renderMarkdown("```js\nconsole.log('hi')\n```");
    expect(container.querySelector("pre")).not.toBeNull();
    expect(container.textContent).toContain("console.log");
  });

  it("renders inline code", () => {
    const { container } = renderMarkdown("use `npm install` to install");
    expect(container.querySelector("code")).not.toBeNull();
    expect(container.textContent).toContain("npm install");
  });

  it("renders tables", () => {
    const md = "| Name | Value |\n| --- | --- |\n| A | 1 |\n| B | 2 |";
    const { container } = renderMarkdown(md);
    expect(container.querySelector("table")).not.toBeNull();
    expect(container.textContent).toContain("Name");
    expect(container.textContent).toContain("A");
  });

  it("strips <script> tags (XSS protection)", () => {
    const { container } = renderMarkdown("<script>alert('xss')</script>");
    expect(container.querySelector("script")).toBeNull();
  });

  it("strips on* event handlers (XSS protection)", () => {
    const { container } = renderMarkdown('<img src="x" onerror="alert(1)" />');
    const img = container.querySelector("img");
    expect(img?.getAttribute("onerror")).toBeNull();
  });

  it("strips javascript: protocol links (XSS protection)", () => {
    const { container } = renderMarkdown(
      '<a href="javascript:alert(1)">click</a>',
    );
    const link = container.querySelector("a");
    const href = link?.getAttribute("href") ?? "";
    expect(href).not.toContain("javascript:");
  });

  it("renders server glossary <term> markup as styled span", () => {
    const { container } = renderMarkdown('<term data-id="PE">PE</term> 是关键');
    const span = container.querySelector("span.term-inline");
    expect(span).not.toBeNull();
    expect(span?.textContent).toContain("PE");
  });

  it("opens term popover on click", () => {
    renderMarkdown('<term data-id="PE">PE</term> 是关键');
    fireEvent.click(screen.getByRole("button", { name: "PE" }));
    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.textContent).toContain("市盈率");
    expect(tooltip.textContent).toContain("花多少钱买1元年利润");
  });

  it("strips <iframe> (XSS protection)", () => {
    const { container } = renderMarkdown(
      '<iframe src="https://evil.com"></iframe>',
    );
    expect(container.querySelector("iframe")).toBeNull();
  });
});
