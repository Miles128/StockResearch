import { useState, useRef, useEffect, type ReactNode } from "react";
import { useI18n } from "./i18n";
import { api, type GlossaryTerm } from "./api";

interface TermPopoverProps {
  term: GlossaryTerm;
  children: ReactNode;
}

/** 投顾模式专有名词弹窗：点击术语展开通俗解释 + 类比。 */
export function TermPopover({ term, children }: TermPopoverProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const { t } = useI18n();

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <span
      ref={ref}
      className="term-inline"
      onClick={() => setOpen((v) => !v)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") setOpen((v) => !v);
      }}
    >
      {children}
      {open && (
        <span className="term-popover" role="tooltip">
          <span className="term-popover-title">
            {term.short}
            {term.en && <span className="term-popover-en">{term.en}</span>}
          </span>
          <span className="term-popover-def">{term.def}</span>
          {term.analogy && (
            <span className="term-popover-analogy">
              💡 {t("termAnalogyLabel")}：{term.analogy}
            </span>
          )}
        </span>
      )}
    </span>
  );
}

// ── 词库获取（模块级缓存，全应用只拉取一次） ──

let _glossaryCache: Record<string, GlossaryTerm> | null = null;
let _glossaryPromise: Promise<Record<string, GlossaryTerm>> | null = null;

function fetchGlossary(): Promise<Record<string, GlossaryTerm>> {
  if (_glossaryCache) return Promise.resolve(_glossaryCache);
  if (!_glossaryPromise) {
    _glossaryPromise = api
      .glossary()
      .then((list) => {
        const map: Record<string, GlossaryTerm> = {};
        for (const item of list) map[item.id] = item;
        _glossaryCache = map;
        return map;
      })
      .catch(() => {
        // 失败则允许下次重试
        _glossaryPromise = null;
        return {};
      });
  }
  return _glossaryPromise;
}

/** 获取词库映射；首次挂载时异步拉取，之后命中模块缓存。 */
export function useGlossary(): Record<string, GlossaryTerm> | null {
  const [glossary, setGlossary] = useState<Record<string, GlossaryTerm> | null>(
    _glossaryCache,
  );
  useEffect(() => {
    if (_glossaryCache) return;
    let active = true;
    fetchGlossary().then((g) => {
      if (active) setGlossary(g);
    });
    return () => {
      active = false;
    };
  }, []);
  return glossary;
}
