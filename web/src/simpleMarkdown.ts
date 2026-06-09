export function simpleMarkdown(text: string): string {
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, _lang: string, code: string) =>
    `<pre class="code-block"><code>${code.trim()}</code></pre>`,
  );

  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^## (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^# (.+)$/gm, "<h3>$1</h3>");

  html = html.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

  html = html.replace(/^(\|.+\|)\n(\|[-| :]+\|)\n((?:\|.+\|\n?)*)/gm, (_m, header: string, _sep: string, body: string) => {
    const thCells = header
      .split("|")
      .filter((c: string) => c.trim())
      .map((c: string) => `<th>${c.trim()}</th>`)
      .join("");
    const rows = body
      .trim()
      .split("\n")
      .map((row: string) => {
        const cells = row
          .split("|")
          .filter((c: string) => c.trim())
          .map((c: string) => `<td>${c.trim()}</td>`)
          .join("");
        return `<tr>${cells}</tr>`;
      })
      .join("");
    return `<table class="metrics-table"><thead><tr>${thCells}</tr></thead><tbody>${rows}</tbody></table>`;
  });

  html = html.replace(/^[-•*] (.+)$/gm, "<li>$1</li>");
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, "<ul>$1</ul>");

  html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");

  html = html.replace(/^---+$/gm, "<hr/>");

  html = html.replace(/\n{2,}/g, "</p><p>");
  html = html.replace(/\n/g, "<br>");

  // Strip dangerous protocol handlers and event attributes as safety net
  html = html.replace(/\b(on\w+)\s*=\s*["'][^"']*["']/gi, "");
  html = html.replace(/\b(href|src)\s*=\s*["']\s*(javascript|vbscript|data):[^"']*["']/gi, "");

  return `<p>${html}</p>`;
}
