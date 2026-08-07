import { useMemo } from "react";
import type { GlossaryTerm } from "./api";
import { useGlossaryContext } from "./GlossaryContext";
import { useI18n } from "./i18n";

/** 术语长度下限：太短的词（如"PE"）单独出现容易误匹配，跳过。 */
const MIN_TERM_LEN = 2;
/** 一次最多展示的概念数（避免刷屏）。 */
const MAX_CARDS = 2;

/**
 * Phase 13a 场景化知识卡片：在用户正在查看的内容（研报结论/因子/筛选结果）
 * 中零点击检测高频金融概念，用词库渲染"这是什么 + 为什么重要"解释卡。
 * 教机制，不给结论；只解释，不打断。
 */
export function KnowledgeCard({ text }: { text: string }) {
  const { enabled, terms } = useGlossaryContext();
  const { t } = useI18n();

  const matched = useMemo(() => {
    if (!enabled || !text) return [];
    const hits: Array<{ term: GlossaryTerm; at: number }> = [];
    for (const term of Object.values(terms)) {
      if (term.short.length < MIN_TERM_LEN) continue;
      const idx = text.indexOf(term.short);
      if (idx >= 0) {
        hits.push({ term, at: idx });
      }
    }
    hits.sort((a, b) => a.at - b.at);
    return hits.slice(0, MAX_CARDS);
  }, [enabled, terms, text]);

  if (matched.length === 0) return null;

  return (
    <div className="knowledge-card-row">
      {matched.map(({ term }) => (
        <details key={term.id} className="knowledge-card">
          <summary>
            <span className="knowledge-card-term">{term.short}</span>
            <span className="knowledge-card-why">{t("knowledge.whyImportant")}</span>
          </summary>
          <div className="knowledge-card-body">
            <p>{term.def}</p>
            {term.analogy ? <p className="muted knowledge-card-analogy">{term.analogy}</p> : null}
          </div>
        </details>
      ))}
    </div>
  );
}
