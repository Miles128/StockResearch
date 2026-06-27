import { describe, it, expect } from "vitest";
import type { ComponentProps } from "react";
import { render } from "@testing-library/react";
import { MarkdownContent } from "../MarkdownContent";
import { I18nProvider } from "../i18n";

function renderMarkdown(text: string, props: Partial<ComponentProps<typeof MarkdownContent>> = {}) {
  return render(
    <I18nProvider>
      <MarkdownContent text={text} {...props} />
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
    const { container } = renderMarkdown('<a href="javascript:alert(1)">click</a>');
    const link = container.querySelector("a");
    // sanitize 移除危险协议链接，href 不应包含 javascript:
    const href = link?.getAttribute("href") ?? "";
    expect(href).not.toContain("javascript:");
  });

  it("renders server glossary <term> markup as styled span", () => {
    const { container } = renderMarkdown('<term data-id="pe">市盈率</term> 是关键');
    const span = container.querySelector("span.term-inline");
    expect(span).not.toBeNull();
    expect(span?.getAttribute("data-term-id")).toBe("pe");
    expect(span?.textContent).toContain("市盈率");
  });

  it("strips <iframe> (XSS protection)", () => {
    const { container } = renderMarkdown('<iframe src="https://evil.com"></iframe>');
    expect(container.querySelector("iframe")).toBeNull();
  });
});
