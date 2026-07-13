import type { AshareFactor, DimensionEvidence, NumericFactor, ResearchReport } from "./api";
import { useI18n } from "./i18n";

function collectEvidence(report: ResearchReport, limit = 3): DimensionEvidence[] {
  const items: DimensionEvidence[] = [];
  for (const dim of Object.values(report.dimensions ?? {})) {
    for (const ev of dim.evidence ?? []) {
      items.push(ev);
      if (items.length >= limit) return items;
    }
  }
  return items;
}

function gapFollowUp(gap: string): string {
  return `补充数据：${gap}`;
}

function missingFromFactors(factors?: AshareFactor[], limit = 3): string[] {
  const out: string[] = [];
  for (const f of factors ?? []) {
    for (const m of f.missing ?? []) {
      if (!out.includes(m)) out.push(m);
      if (out.length >= limit) return out;
    }
  }
  return out;
}

export function ResearchTrustStrip({
  report,
  compact = false,
  onFollowUp,
}: {
  report: ResearchReport;
  compact?: boolean;
  onFollowUp?: (query: string) => void;
}) {
  const { t } = useI18n();
  const gaps = [
    ...(report.data_gaps ?? []).slice(0, 3),
    ...missingFromFactors(report.ashare_factors, 2),
  ].filter((g, i, arr) => arr.indexOf(g) === i).slice(0, 4);
  const evidence = collectEvidence(report, compact ? 2 : 3);
  const factors = (report.factors ?? []).slice(0, compact ? 3 : 4);
  const provenance = report.bars_provenance;

  if (!gaps.length && !evidence.length && !factors.length && !provenance) {
    return null;
  }

  return (
    <div className={`research-trust-strip ${compact ? "compact" : ""}`}>
      <div className="research-trust-title">{t("card.trustStrip")}</div>
      {provenance ? (
        <p className="muted research-trust-line">
          <strong>{t("card.barsProvenance")}：</strong>
          {provenance.adjust}/{provenance.source}
          {provenance.as_of ? ` · ${provenance.as_of}` : ""}
          {provenance.partial ? ` · ${t("card.factorPartial")}` : ""}
          {provenance.note ? ` · ${provenance.note}` : ""}
        </p>
      ) : null}
      {gaps.length > 0 && (
        <div className="research-trust-block">
          <strong>{t("card.dataGaps")}</strong>
          <div className="follow-up-row">
            {gaps.map((gap) =>
              onFollowUp ? (
                <button
                  key={gap}
                  type="button"
                  className="example-chip"
                  onClick={() => onFollowUp(gapFollowUp(gap))}
                >
                  {gap}
                </button>
              ) : (
                <span key={gap} className="example-chip static">
                  {gap}
                </span>
              ),
            )}
          </div>
        </div>
      )}
      {evidence.length > 0 && (
        <div className="research-trust-block">
          <strong>{t("card.evidence")}</strong>
          <ul className="research-trust-list">
            {evidence.map((ev, i) => (
              <li key={`${ev.source}-${i}`}>
                <span className="muted">
                  {ev.kind || ev.source}
                  {ev.date ? ` · ${ev.date}` : ""}
                </span>
                {" — "}
                {ev.snippet}
              </li>
            ))}
          </ul>
        </div>
      )}
      {factors.length > 0 && (
        <div className="research-trust-block">
          <strong>{t("card.numericFactors")}</strong>
          <div className="follow-up-row">
            {factors.map((f: NumericFactor) => (
              <span
                key={f.key}
                className={`example-chip ${f.partial ? "" : "active"}`}
                title={f.note || undefined}
              >
                {f.label}{" "}
                {f.value != null ? `${f.value}${f.unit || ""}` : "—"}
                {f.partial ? ` · ${t("card.factorPartial")}` : ""}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
