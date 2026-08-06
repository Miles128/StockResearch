import ReactMarkdown, { type Components } from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { memo, useMemo, type ReactNode } from "react";
import { useGlossaryContext } from "./GlossaryContext";
import { TermPopover, useGlossary } from "./TermPopover";

// 扩展默认 sanitize schema：允许服务端 glossary 生成的 <term data-id> 标签。
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

function resolveTermId(props: Record<string, unknown>): string {
  const node = props.node as { properties?: Record<string, unknown> } | undefined;
  const properties = node?.properties ?? {};
  return String(
    properties.dataId ?? properties["data-id"] ?? props.dataId ?? props["data-id"] ?? "",
  );
}

export const MarkdownContent = memo(function MarkdownContent({
  text,
  className = "markdown-body",
}: MarkdownContentProps) {
  const { enabled, terms: contextTerms } = useGlossaryContext();
  const fetchedTerms = useGlossary();
  const glossary = useMemo(() => {
    if (Object.keys(contextTerms).length > 0) return contextTerms;
    return fetchedTerms ?? {};
  }, [contextTerms, fetchedTerms]);

  const components = useMemo(() => {
    const renderTerm = (props: Record<string, unknown>) => {
      const dataId = resolveTermId(props);
      const child = props.children as ReactNode;
      if (!enabled) {
        return <span>{child}</span>;
      }
      const termInfo = glossary[dataId];
      if (!termInfo) {
        return (
          <span className="term-inline" data-term-id={dataId}>
            {child}
          </span>
        );
      }
      return <TermPopover term={termInfo}>{child}</TermPopover>;
    };

    return {
      a: ({ href, children }: { href?: string; children?: ReactNode }) => (
        <a href={href} target="_blank" rel="noreferrer">
          {children}
        </a>
      ),
      term: renderTerm,
    } as unknown as Components;
  }, [enabled, glossary]);

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
});
