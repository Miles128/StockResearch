import type { MarketOverview } from "./api";
import { signedClass } from "./holdingDisplay";
import { QuoteValues } from "./ui/DataValue";
import { useI18n } from "./i18n";
import { localizeIndexName } from "./indexLabels";
import { TickerSparkline } from "./TickerSparkline";

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

  return (
    <div className="market-ticker-wrap market-ticker-oneline">
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
              <TickerSparkline changePct={idx.change_pct ?? 0} />
              <span className="ticker-card-content">
                <span className="ticker-name">{label}</span>
                <QuoteValues
                  inline
                  price={idx.price}
                  changePct={idx.change_pct ?? 0}
                  priceClassName="ticker-price"
                />
              </span>
            </button>
          );
        })}
        {!overview?.indices?.length && loading && (
          <div className="ticker-skeleton" aria-busy="true">
            <div className="skeleton-block" />
            <div className="skeleton-block" />
            <div className="skeleton-block" />
          </div>
        )}
        {!overview?.indices?.length && !loading && (
          <div className="ticker-card ticker-card-empty">
            <span className="muted">—</span>
          </div>
        )}
        {overview?.northbound_net_yi != null && (
          <span className={`ticker-inline-meta ${signedClass(overview.northbound_net_yi)}`}>
            {northboundLabel.replace("{v}", overview.northbound_net_yi.toFixed(1))}
          </span>
        )}
        {overview?.advancers != null && overview?.decliners != null && (
          <span className="ticker-inline-meta muted">
            {breadthLabel
              .replace("{up}", String(overview.advancers))
              .replace("{down}", String(overview.decliners))}
          </span>
        )}
        <span className="ticker-session-inline">{sessionLabel}</span>
      </div>
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
