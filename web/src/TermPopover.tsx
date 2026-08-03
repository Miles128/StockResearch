import {
  useState,
  useRef,
  useEffect,
  useLayoutEffect,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { useI18n } from "./i18n";
import { api, type GlossaryTerm } from "./api";

interface TermPopoverProps {
  term: GlossaryTerm;
  children: ReactNode;
}

interface PopoverPosition {
  top: number;
  left: number;
}

/** 投顾模式专有名词弹窗：点击术语展开通俗解释 + 类比。 */
export function TermPopover({ term, children }: TermPopoverProps) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<PopoverPosition | null>(null);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const { t } = useI18n();

  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const popoverWidth = 280;
    const left = Math.min(
      Math.max(12, rect.left + rect.width / 2 - popoverWidth / 2),
      window.innerWidth - popoverWidth - 12,
    );
    setPosition({ top: rect.top - 8, left: left + popoverWidth / 2 });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (
        triggerRef.current &&
        !triggerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    function handleScroll() {
      setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    window.addEventListener("scroll", handleScroll, true);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      window.removeEventListener("scroll", handleScroll, true);
    };
  }, [open]);

  return (
    <>
      <span
        ref={triggerRef}
        className="term-inline"
        onClick={() => setOpen((v) => !v)}
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setOpen((v) => !v);
          }
        }}
      >
        {children}
      </span>
      {open &&
        position &&
        createPortal(
          <span
            className="term-popover term-popover-fixed"
            role="tooltip"
            style={{
              top: position.top,
              left: position.left,
            }}
          >
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
          </span>,
          document.body,
        )}
    </>
  );
}

// ── 词库获取（模块级缓存，全应用只拉取一次） ──

let _glossaryCache: Record<string, GlossaryTerm> | null = null;
let _glossaryPromise: Promise<Record<string, GlossaryTerm>> | null = null;

export function seedGlossaryCache(terms: Record<string, GlossaryTerm>): void {
  _glossaryCache = terms;
}

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
