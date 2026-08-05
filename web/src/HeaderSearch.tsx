import { useEffect, useRef, useState } from "react";
import { api, type StockLookupOut } from "./api";
import { useI18n } from "./i18n";

interface HeaderSearchProps {
  onSelectStock: (symbol: string, name: string) => void;
  onAskQuery: (query: string) => void;
}

export function HeaderSearch({ onSelectStock, onAskQuery }: HeaderSearchProps) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [lookup, setLookup] = useState<StockLookupOut | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      // 输入不足时同步清空结果：派生状态重置，属预期级联
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLookup(null);
      return;
    }
    const timer = window.setTimeout(() => {
      setLoading(true);
      api
        .lookupStock(q)
        .then(setLookup)
        .catch(() => setLookup(null))
        .finally(() => setLoading(false));
    }, 280);
    return () => window.clearTimeout(timer);
  }, [query]);

  function submit() {
    const q = query.trim();
    if (!q) return;
    if (lookup?.status === "confirmed" && lookup.symbol && lookup.name) {
      onSelectStock(lookup.symbol, lookup.name);
      setQuery("");
      setLookup(null);
      return;
    }
    onAskQuery(q);
    setQuery("");
    setLookup(null);
  }

  function pickCandidate(symbol: string, name: string) {
    onSelectStock(symbol, name);
    setQuery("");
    setLookup(null);
  }

  const showDropdown = query.trim().length >= 2 && (loading || lookup);
  const showCandidates =
    lookup &&
    (lookup.status === "ambiguous" || lookup.status === "confirmed") &&
    lookup.candidates.length > 0;

  return (
    <div className="chrome-search-wrap" ref={wrapRef}>
      <input
        ref={inputRef}
        className="chrome-search-input"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") submit();
          if (e.key === "Escape") {
            setQuery("");
            setLookup(null);
            inputRef.current?.blur();
          }
        }}
        placeholder={t("search.placeholder")}
      />
      {showDropdown && (
        <div className="search-suggest" role="listbox">
          {loading && <div className="search-suggest-item muted">{t("search.searching")}</div>}
          {!loading &&
            showCandidates &&
            lookup.candidates.map((c) => (
              <button
                key={c.symbol}
                type="button"
                className="search-suggest-item"
                onClick={() => pickCandidate(c.symbol, c.name)}
              >
                <span>{c.name}</span>
                <span className="mono muted">{c.symbol}</span>
              </button>
            ))}
          {!loading && lookup?.status === "not_found" && (
            <div className="search-suggest-item muted">{t("search.notFound")}</div>
          )}
        </div>
      )}
    </div>
  );
}
