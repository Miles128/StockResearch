import { useState } from "react";
import { api, type StockLookupOut } from "./api";
import { useI18n } from "./i18n";

interface WatchlistAddPanelProps {
  onAdd: (symbol: string, name: string) => void | Promise<void>;
  onCancel?: () => void;
}

export function WatchlistAddPanel({ onAdd, onCancel }: WatchlistAddPanelProps) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [lookup, setLookup] = useState<StockLookupOut | null>(null);
  const [error, setError] = useState("");

  async function runLookup(raw: string) {
    const trimmed = raw.trim();
    if (!trimmed) return;
    setLoading(true);
    setError("");
    setLookup(null);
    try {
      const result = await api.lookupStock(trimmed);
      if (result.status === "confirmed" && result.symbol && result.name) {
        await onAdd(result.symbol, result.name);
        setQuery("");
        return;
      }
      if (result.status === "ambiguous" && result.candidates.length > 0) {
        setLookup(result);
        return;
      }
      setError(result.message || t("search.notFound"));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function pickCandidate(symbol: string, name: string) {
    setLoading(true);
    setError("");
    try {
      await onAdd(symbol, name);
      setQuery("");
      setLookup(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="lists-watchlist-add-panel">
      <form
        className="lists-watchlist-add"
        onSubmit={(e) => {
          e.preventDefault();
          void runLookup(query);
        }}
      >
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setLookup(null);
            setError("");
          }}
          placeholder={t("lists.watchlistAddPh")}
          disabled={loading}
          autoFocus
        />
        <button
          type="submit"
          className="btn btn-primary btn-sm"
          disabled={loading || !query.trim()}
        >
          {loading ? t("search.searching") : t("lists.watchlistAdd")}
        </button>
        {onCancel && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onCancel}
            disabled={loading}
          >
            {t("settings.cancel")}
          </button>
        )}
      </form>
      {lookup?.status === "ambiguous" && lookup.candidates.length > 0 && (
        <div
          className="lists-watchlist-candidates"
          role="listbox"
          aria-label={t("lists.watchlistPick")}
        >
          <p className="muted lists-watchlist-candidates-hint">
            {lookup.message || t("lists.watchlistPick")}
          </p>
          {lookup.candidates.map((c) => (
            <button
              key={c.symbol}
              type="button"
              className="lists-watchlist-candidate"
              onClick={() => void pickCandidate(c.symbol, c.name)}
              disabled={loading}
            >
              <span>{c.name}</span>
              <span className="mono">{c.symbol}</span>
            </button>
          ))}
        </div>
      )}
      {error && <p className="error lists-watchlist-add-error">{error}</p>}
    </div>
  );
}
