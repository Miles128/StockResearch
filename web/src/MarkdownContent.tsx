import ReactMarkdown, { type Components } from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import type { ReactNode } from "react";
import type { GlossaryTerm } from "./api";
import { useI18n } from "./i18n";
import { TermPopover } from "./TermPopover";

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
  className?: string;
  enableGlossary?: boolean;
  glossary?: Record<string, GlossaryTerm>;
}

function buildTermComponent(
  enableGlossary: boolean,
  glossary: Record<string, GlossaryTerm>,
  t: (key: string) => string,
) {
  return function TermComponent(props: Record<string, unknown>) {
    const node = props.node as { properties?: Record<string, unknown> } | undefined;
    const properties = node?.properties ?? {};
    const dataId = String(
      properties.dataId ?? properties["data-id"] ?? props.dataId ?? props["data-id"] ?? "",
    );
    const children = props.children as ReactNode;
    if (!enableGlossary || !dataId) {
      return (
        <span className="term-inline" data-term-id={dataId}>
          {children}
        </span>
      );
    }
    const term = glossary[dataId] || {
      id: dataId,
      short: dataId,
      en: "",
      def: t("term.aiGenerated"),
      analogy: "",
    };
    return (
      <TermPopover term={term}>
        {children}
      </TermPopover>
    );
  };
}

export function MarkdownContent({
  text,
  className = "markdown-body",
  enableGlossary = false,
  glossary = {},
}: MarkdownContentProps) {
  const { t } = useI18n();
  const components = {
    a: ({ href, children }: { href?: string; children?: ReactNode }) => (
      <a href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    ),
    term: buildTermComponent(enableGlossary, glossary, t),
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
