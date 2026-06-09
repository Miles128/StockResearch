import { describe, it, expect } from "vitest";
import { simpleMarkdown } from "../simpleMarkdown";

describe("simpleMarkdown", () => {
  it("renders basic text", () => {
    const result = simpleMarkdown("hello world");
    expect(result).toContain("hello world");
  });

  it("escapes HTML tags", () => {
    const result = simpleMarkdown("<script>alert('xss')</script>");
    expect(result).not.toContain("<script>");
    expect(result).toContain("&lt;script&gt;");
  });

  it("strips on* event handlers (XSS protection)", () => {
    const result = simpleMarkdown('img onerror="alert(1)"');
    expect(result).not.toContain("onerror");
  });

  it("strips javascript: protocol links (XSS protection)", () => {
    const result = simpleMarkdown('href="javascript:alert(1)"');
    expect(result).not.toContain("javascript:");
  });

  it("strips vbscript: protocol links (XSS protection)", () => {
    const result = simpleMarkdown('href="vbscript:alert(1)"');
    expect(result).not.toContain("vbscript:");
  });

  it("renders code blocks", () => {
    const result = simpleMarkdown("```js\nconsole.log('hi')\n```");
    expect(result).toContain("<pre");
    expect(result).toContain("<code>");
    expect(result).toContain("console.log");
  });

  it("renders inline code", () => {
    const result = simpleMarkdown("use `npm install` to install");
    expect(result).toContain("<code>npm install</code>");
  });

  it("renders bold text", () => {
    const result = simpleMarkdown("this is **bold** text");
    expect(result).toContain("<strong>bold</strong>");
  });

  it("renders italic text", () => {
    const result = simpleMarkdown("this is *italic* text");
    expect(result).toContain("<em>italic</em>");
  });

  it("renders bold+italic text", () => {
    const result = simpleMarkdown("this is ***both*** text");
    expect(result).toContain("<strong><em>both</em></strong>");
  });

  it("renders tables", () => {
    const md = "| Name | Value |\n| --- | --- |\n| A | 1 |\n| B | 2 |";
    const result = simpleMarkdown(md);
    expect(result).toContain("<table");
    expect(result).toContain("<th>Name</th>");
    expect(result).toContain("<td>A</td>");
    expect(result).toContain("<td>B</td>");
  });

  it("renders headings", () => {
    const result = simpleMarkdown("# Title");
    expect(result).toContain("<h3>Title</h3>");
  });

  it("renders unordered lists", () => {
    const result = simpleMarkdown("- item1\n- item2");
    expect(result).toContain("<ul>");
    expect(result).toContain("<li>item1</li>");
    expect(result).toContain("<li>item2</li>");
  });

  it("renders horizontal rules", () => {
    const result = simpleMarkdown("---");
    expect(result).toContain("<hr/>");
  });
});
