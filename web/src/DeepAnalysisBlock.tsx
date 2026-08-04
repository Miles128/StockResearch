import type {
  ImpactOut,
  ImpactPeakDayOut,
  PricingBridgeOut,
  ResearchReport,
  ThesisOut,
} from "./api";
import { useI18n } from "./i18n";

function fmtPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function PeakDayRow({
  day,
  t,
}: {
  day: ImpactPeakDayOut;
  t: (key: string, params?: Record<string, string | number>) => string;
}) {
  const eventLabel = day.event_kind ? t(`card.impactEventKind.${day.event_kind}`) : null;
  return (
    <li className={`impact-peak-day${day.unexplained ? " unexplained" : ""}`}>
      <span className="impact-peak-date">{day.date}</span>
      <span className="impact-peak-idio">{fmtPct(day.idio_return_pct)}</span>
      {eventLabel || day.event_title ? (
        <span className="impact-peak-event">
          {eventLabel ? `${eventLabel} · ` : ""}
          {day.event_title ?? ""}
        </span>
      ) : (
        <span className="impact-peak-event muted">{t("card.impactUnexplained")}</span>
      )}
      {day.event_fwd_return_5d_pct != null && (
        <span className="impact-peak-fwd muted">
          {t("card.impactFwd5d", {
            value: fmtPct(day.event_fwd_return_5d_pct),
          })}
        </span>
      )}
    </li>
  );
}

function ImpactBlock({
  impact,
  t,
}: {
  impact: ImpactOut;
  t: (key: string, params?: Record<string, string | number>) => string;
}) {
  const stats: { label: string; value: string }[] = [
    { label: t("card.impactStock"), value: fmtPct(impact.stock_return_pct) },
    { label: t("card.impactMarket"), value: fmtPct(impact.market_contrib_pct) },
    {
      label: t("card.impactIndustry"),
      value: fmtPct(impact.industry_contrib_pct),
    },
    { label: t("card.impactIdio"), value: fmtPct(impact.idio_return_pct) },
  ];
  return (
    <div className="impact-block">
      <div className="impact-stats-row">
        {stats.map((s) => (
          <span key={s.label} className="stat-pill impact-stat">
            <span className="impact-stat-label">{s.label}</span>
            <span className="impact-stat-value">{s.value}</span>
          </span>
        ))}
      </div>
      <p className="muted impact-meta">
        {t("card.impactWindow", { days: String(impact.window_trading_days) })}
        {impact.r_squared != null
          ? ` · ${t("card.impactRSquared", { value: impact.r_squared!.toFixed(2) })}`
          : ""}
        {impact.market_symbol
          ? ` · ${t("card.impactMarketSymbol", { symbol: impact.market_symbol })}`
          : ""}
        {impact.industry_proxy
          ? ` · ${t("card.impactIndustryProxy", { proxy: impact.industry_proxy })}`
          : ""}
        {impact.partial ? ` · ${t("card.factorPartial")}` : ""}
      </p>
      {impact.peak_days && impact.peak_days.length > 0 && (
        <div className="impact-peak-days">
          <strong>{t("card.impactPeakDays")}</strong>
          <ul className="impact-peak-list">
            {impact.peak_days.map((day) => (
              <PeakDayRow key={day.date} day={day} t={t} />
            ))}
          </ul>
        </div>
      )}
      {impact.gaps && impact.gaps.length > 0 && (
        <p className="muted impact-gaps">
          <strong>{t("card.dataGaps")}：</strong>
          {impact.gaps.join("；")}
        </p>
      )}
    </div>
  );
}

function PricingBlock({
  pricing,
  t,
}: {
  pricing: PricingBridgeOut;
  t: (key: string, params?: Record<string, string | number>) => string;
}) {
  const stats: { label: string; value: string }[] = [
    {
      label: t("card.pricingPriceChange"),
      value: fmtPct(pricing.price_change_pct),
    },
    {
      label: t("card.pricingEarnings"),
      value: fmtPct(pricing.earnings_contrib_pct),
    },
    {
      label: t("card.pricingMultiple"),
      value: fmtPct(pricing.multiple_contrib_pct),
    },
  ];
  return (
    <div className="pricing-block">
      <p className="pricing-title">{t("card.pricingTitle")}</p>
      <div className="impact-stats-row">
        {stats.map((s) => (
          <span key={s.label} className="stat-pill impact-stat">
            <span className="impact-stat-label">{s.label}</span>
            <span className="impact-stat-value">{s.value}</span>
          </span>
        ))}
      </div>
      <p className="muted impact-meta">
        {pricing.window_label ? ` · ${pricing.window_label}` : ""}
        {pricing.pe_end != null ? ` · PE(TTM) ${pricing.pe_end.toFixed(2)}` : ""}
        {pricing.pe_start != null ? ` · PE 起 ${pricing.pe_start.toFixed(2)}` : ""}
        {pricing.partial ? ` · ${t("card.factorPartial")}` : ""}
      </p>
      {pricing.gaps && pricing.gaps.length > 0 && (
        <p className="muted impact-gaps">
          <strong>{t("card.dataGaps")}：</strong>
          {pricing.gaps.join("；")}
        </p>
      )}
    </div>
  );
}

function ThesisBlock({
  thesis,
  t,
}: {
  thesis: ThesisOut;
  t: (key: string, params?: Record<string, string | number>) => string;
}) {
  return (
    <div className="thesis-block">
      <p className="thesis-title">{t("card.thesisTitle")}</p>
      <p className="thesis-claim">{thesis.claim}</p>
      {thesis.horizon ? (
        <p className="muted thesis-horizon">
          {t("card.thesisHorizon", { horizon: thesis.horizon })}
        </p>
      ) : null}
      {thesis.monitors && thesis.monitors.length > 0 && (
        <div className="thesis-list-block">
          <strong>{t("card.thesisMonitors")}</strong>
          <ul className="thesis-list">
            {thesis.monitors.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}
      {thesis.invalidate_if && thesis.invalidate_if.length > 0 && (
        <div className="thesis-list-block">
          <strong>{t("card.thesisInvalidateIf")}</strong>
          <ul className="thesis-list">
            {thesis.invalidate_if.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
      {thesis.evidence_ids && thesis.evidence_ids.length > 0 && (
        <p className="muted thesis-evidence">
          <strong>{t("card.thesisEvidence")}</strong>
          {thesis.evidence_ids.join(" · ")}
        </p>
      )}
      {thesis.partial ? <p className="muted thesis-partial">{t("card.factorPartial")}</p> : null}
    </div>
  );
}

export function DeepAnalysisBlock({
  report,
  compact = false,
}: {
  report: ResearchReport;
  compact?: boolean;
}) {
  const { t } = useI18n();
  const impact = report.deep_analysis?.impact;
  const pricing = report.deep_analysis?.pricing;
  const thesis = report.deep_analysis?.thesis;
  if (!impact && !pricing && !thesis) return null;
  return (
    <details className={`deep-analysis-block${compact ? " compact" : ""}`} open={!compact}>
      <summary>{t("card.deepAnalysisTitle")}</summary>
      {impact ? <ImpactBlock impact={impact} t={t} /> : null}
      {pricing ? <PricingBlock pricing={pricing} t={t} /> : null}
      {thesis ? <ThesisBlock thesis={thesis} t={t} /> : null}
    </details>
  );
}
