import type { MarketOverview } from "./api";
import { formatPrice, formatSignedPct, signedClass } from "./holdingDisplay";
import { useI18n } from "./i18n";
import { localizeIndexName } from "./indexLabels";

export function MarketTicker({
  overview,
  loading,
  sessionLabel,
  northboundLabel,
  breadthLabel,
  refreshTitle,
  onRefresh,
  onIndexClick,
}: {
  overview: MarketOverview | null;
  loading: boolean;
  sessionLabel: string;
  northboundLabel: string;
  breadthLabel: string;
  refreshTitle: string;
  onRefresh: () => void;
  onIndexClick: (name: string) => void;
}) {
  const { t } = useI18n();
  const hasMeta =
    overview?.northbound_net_yi != null ||
    (overview?.advancers != null && overview?.decliners != null);

  return (
    <div className="market-ticker-wrap">
      <div className="ticker-strip">
        {(overview?.indices ?? []).map((idx) => {
          const label = localizeIndexName(idx.symbol, idx.name, t);
          return (
          <button
            key={idx.symbol ?? idx.name}
            type="button"
            className="ticker-card ticker-card-btn"
            onClick={() => onIndexClick(label)}
            title={label}
          >
            <div className="ticker-name">{label}</div>
            <div className="ticker-price mono">{formatPrice(idx.price)}</div>
            <div className={`ticker-change mono ${signedClass(idx.change_pct)}`}>
              {formatSignedPct(idx.change_pct)}
            </div>
          </button>
          );
        })}
        {!overview?.indices?.length && (
          <div className="ticker-card ticker-card-empty">
            <span className="muted">{loading ? "…" : "—"}</span>
          </div>
        )}
        <span className="ticker-session-inline">{sessionLabel}</span>
      </div>
      {hasMeta && (
        <div className="ticker-meta">
          {overview?.northbound_net_yi != null && (
            <span className={signedClass(overview.northbound_net_yi)}>
              {northboundLabel.replace("{v}", overview.northbound_net_yi.toFixed(1))}
            </span>
          )}
          {overview?.advancers != null && overview?.decliners != null && (
            <span className="muted">
              {breadthLabel
                .replace("{up}", String(overview.advancers))
                .replace("{down}", String(overview.decliners))}
            </span>
          )}
        </div>
      )}
      <button
        type="button"
        className="ticker-refresh-hidden"
        onClick={onRefresh}
        disabled={loading}
        aria-label={refreshTitle}
        title={refreshTitle}
      />
    </div>
  );
}
