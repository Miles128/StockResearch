import ReactMarkdown, { type Components } from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import type { ReactNode } from "react";
import { TermPopover, useGlossary } from "./TermPopover";

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

export function MarkdownContent({ text, className = "markdown-body" }: MarkdownContentProps) {
  // 投顾模式后端会标记 <term>；投研模式不标记，glossary 拉取后也无处使用。
  // 模块级缓存保证全应用只拉取一次。
  const glossary = useGlossary();

  // react-markdown 的 Components 类型不包含自定义 <term> 标签，
  // 用类型断言绕过；运行时 react-markdown 会将 <term> 节点传给该渲染器。
  // hast 将 data-id 属性存储为 dataId 属性（property-information camelCase 约定）。
  const components = {
    a: ({ href, children }: { href?: string; children?: ReactNode }) => (
      <a href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    ),
    term: (props: Record<string, unknown>) => {
      const node = props.node as { properties?: Record<string, unknown> } | undefined;
      const properties = node?.properties ?? {};
      const dataId = String(
        properties.dataId ??
          properties["data-id"] ??
          props.dataId ??
          props["data-id"] ??
          "",
      );
      const termInfo = glossary?.[dataId];
      if (!termInfo) {
        // 词库未加载完成或词条缺失：降级为带下划线的纯文本，保持可读。
        return (
          <span className="term-inline" data-term-id={dataId}>
            {props.children as ReactNode}
          </span>
        );
      }
      return <TermPopover term={termInfo}>{props.children as ReactNode}</TermPopover>;
    },
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
