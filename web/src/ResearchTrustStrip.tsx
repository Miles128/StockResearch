import { useState } from "react";
import {
  api,
  type AshareFactor,
  type DimensionEvidence,
  type NumericFactor,
  type ReportPostHoc,
  type ResearchReport,
} from "./api";
import { useI18n } from "./i18n";

function collectEvidence(
  report: ResearchReport,
  limit = 3,
): DimensionEvidence[] {
  const items: DimensionEvidence[] = [];
  for (const dim of Object.values(report.dimensions ?? {})) {
    for (const ev of dim.evidence ?? []) {
      items.push(ev);
      if (items.length >= limit) return items;
    }
  }
  return items;
}

function gapFollowUp(symbol: string, gap: string): string {
  return `补充数据并重新投研 ${symbol}：${gap}。请用综合分析档重新跑四维投研。`;
}

function gapCloseQuery(symbol: string, name: string, gaps: string[]): string {
  const list = gaps.slice(0, 4).join("；");
  return `只补缺口再跑 综合分析${name}（${symbol}）。优先补齐：${list}。请调用 skill_stock_research 重新投研，并在 context 中列出上述缺口。`;
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
  const [postHoc, setPostHoc] = useState<
    ReportPostHoc | "loading" | "error" | null
  >(null);
  const gaps = [
    ...(report.data_gaps ?? []).slice(0, 3),
    ...missingFromFactors(report.ashare_factors, 2),
  ]
    .filter((g, i, arr) => arr.indexOf(g) === i)
    .slice(0, 4);
  const evidence = collectEvidence(report, compact ? 2 : 3);
  const expanded =
    Boolean(report.factors_expanded) || report.analysis_depth !== "standard";
  const factorLimit = compact ? (expanded ? 5 : 3) : expanded ? 8 : 4;
  const factors = (report.factors ?? []).slice(0, factorLimit);
  const provenance = report.bars_provenance;
  const depth = report.analysis_depth ?? "standard";
  const depthLabel =
    depth === "deep"
      ? t("card.analysisDepthDeep")
      : depth === "comprehensive"
        ? t("card.analysisDepthComprehensive")
        : t("card.analysisDepthStandard");
  const canVerify =
    Boolean(report.enable_signal_verify_hook) &&
    typeof report.id === "number" &&
    report.id > 0;

  async function runPostHoc() {
    if (typeof report.id !== "number") return;
    setPostHoc("loading");
    try {
      setPostHoc(await api.reportPostHoc(report.id));
    } catch {
      setPostHoc("error");
    }
  }

  if (
    !gaps.length &&
    !evidence.length &&
    !factors.length &&
    !provenance &&
    !canVerify
  ) {
    return null;
  }

  return (
    <div className={`research-trust-strip ${compact ? "compact" : ""}`}>
      <div className="research-trust-title">
        {t("card.trustStrip")}
        <span className="muted">
          {" "}
          · {t("card.analysisDepthLabel")}：{depthLabel}
        </span>
      </div>
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
            {onFollowUp ? (
              <button
                type="button"
                className="example-chip active"
                onClick={() =>
                  onFollowUp(
                    gapCloseQuery(
                      report.symbol,
                      report.name || report.symbol,
                      gaps,
                    ),
                  )
                }
              >
                {t("card.gapCloseRerun")}
              </button>
            ) : null}
            {gaps.map((gap) =>
              onFollowUp ? (
                <button
                  key={gap}
                  type="button"
                  className="example-chip"
                  onClick={() => onFollowUp(gapFollowUp(report.symbol, gap))}
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
                {f.label} {f.value != null ? `${f.value}${f.unit || ""}` : "—"}
                {f.partial ? ` · ${t("card.factorPartial")}` : ""}
              </span>
            ))}
          </div>
          {report.factor_alignment_note ? (
            <p className="muted research-trust-line">
              <strong>{t("card.factorAlignment")}：</strong>
              {report.factor_alignment_note}
            </p>
          ) : null}
        </div>
      )}
      {canVerify ? (
        <div className="research-trust-block">
          <strong>{t("card.postHoc")}</strong>
          <p className="muted research-trust-line">
            {t("card.signalVerifyHint")}
          </p>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={postHoc === "loading"}
            onClick={() => void runPostHoc()}
          >
            {postHoc === "loading" ? "…" : t("card.postHocBtn")}
          </button>
          {postHoc && postHoc !== "loading" && postHoc !== "error" ? (
            <p className="muted research-trust-line">
              {postHoc.horizons.some((h) => h.return_pct != null)
                ? postHoc.horizons
                    .map((h) =>
                      t("card.postHocRow", {
                        days: String(h.days),
                        ret: h.return_pct != null ? String(h.return_pct) : "—",
                      }),
                    )
                    .join(" · ")
                : t("card.postHocEmpty")}
            </p>
          ) : null}
          {postHoc === "error" ? (
            <p className="muted research-trust-line">
              {t("card.postHocEmpty")}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
