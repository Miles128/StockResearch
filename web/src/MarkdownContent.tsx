import ReactMarkdown, { type Components } from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import type { ReactNode } from "react";

// 扩展默认 sanitize schema：允许服务端 glossary 生成的 <term data-id> 标签。
// 默认 schema 已禁止 script/iframe/event handler/javascript: 协议，安全基线保留。
// 注意：hast 属性名使用 camelCase（property-information 约定），data-id → dataId。
const sanitizeSchema = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames ?? []), "term"],
  attributes: {
    ...(defaultSchema.attributes ?? {}),
    term: ["dataId"],
    span: ["className", "dataTermId"],
  },
};

interface MarkdownContentProps {
  text: string;
  /** Optional className wrapper override (defaults to markdown-body). */
  className?: string;
}

/** Map custom <term> element (server glossary markup) to a styled span.
 *  hast 将 data-id 属性存储为 dataId 属性（property-information camelCase 约定）。 */
function termComponent(props: Record<string, unknown>) {
  const node = props.node as { properties?: Record<string, unknown> } | undefined;
  const properties = node?.properties ?? {};
  const dataId = String(
    properties.dataId ?? properties["data-id"] ?? props.dataId ?? props["data-id"] ?? "",
  );
  return (
    <span className="term-inline" data-term-id={dataId}>
      {props.children as ReactNode}
    </span>
  );
}

export function MarkdownContent({ text, className = "markdown-body" }: MarkdownContentProps) {
  // react-markdown 的 Components 类型不包含自定义 <term> 标签，
  // 用类型断言绕过；运行时 react-markdown 会将 <term> 节点传给 termComponent。
  const components = {
    a: ({ href, children }: { href?: string; children?: ReactNode }) => (
      <a href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    ),
    // Custom glossary term rendered as inline span (popover handled upstream).
    term: termComponent,
  } as unknown as Components;
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, [rehypeSanitize, sanitizeSchema]]}
        components={components}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
