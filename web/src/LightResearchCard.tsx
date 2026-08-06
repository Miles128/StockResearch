import { useState } from "react";
import { api, type ResearchReport } from "./api";
import { DeepAnalysisBlock } from "./DeepAnalysisBlock";
import { DimensionCards, dimensionItemsFromResults } from "./DimensionCards";
import { HypothesisVerifyButton } from "./HypothesisVerifyButton";
import { EVENT_KEYS, recordEvent } from "./usageTracking";
import { useI18n } from "./i18n";
import type { AppMode } from "./modeSettings";
import { MarkdownContent } from "./MarkdownContent";
import { normalizeResearchConclusion, researchExpandHintsFromReport } from "./researchText";
import { ResearchReportDetails } from "./researchReportView";
import { ResearchTrustStrip } from "./ResearchTrustStrip";
import { localizeAgentDisplay, localizeConfidence } from "./uiLabels";

interface LightResearchCardProps {
  report: ResearchReport;
  appMode: AppMode;
  onFollowUp?: (query: string) => void;
}

type ReportView = "brief" | "formal";

export function LightResearchCard({
  report: initialReport,
  appMode,
  onFollowUp,
}: LightResearchCardProps) {
  const { t } = useI18n();
  const [report, setReport] = useState(initialReport);
  const [refilling, setRefilling] = useState(false);
  const [refillError, setRefillError] = useState<string | null>(null);
  const followUps = report.follow_up_questions ?? [];
  const isAdvisor = appMode === "advisor";
  const isExpert = appMode === "research";
  const [view, setView] = useState<ReportView>(isAdvisor ? "brief" : "formal");
  const [downloading, setDownloading] = useState<"md" | "pdf" | "json" | "csv" | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const dimensions = Object.entries(report.dimensions ?? {});
  const brief = isAdvisor && view === "brief";

  const summaryText = brief
    ? report.brief_summary?.trim() ||
      normalizeResearchConclusion(report.summary, {
        minLen: 60,
        maxLen: 160,
        expandHints: researchExpandHintsFromReport(report),
      })
    : normalizeResearchConclusion(report.summary, {
        minLen: 200,
        maxLen: 320,
        expandHints: researchExpandHintsFromReport(report),
      });

  async function handleDownload(kind: "md" | "pdf" | "json" | "csv") {
    setDownloadError(null);
    setDownloading(kind);
    recordEvent(EVENT_KEYS.exportReport);
    try {
      if (kind === "json") {
        await api.exportReportJson(report);
      } else if (kind === "csv") {
        await api.exportReportCsv(report);
      } else if (report.id != null) {
        if (kind === "md") api.downloadReportMarkdown(report.id);
        else api.downloadReportPdf(report.id);
      } else if (kind === "md") {
        await api.exportReportMarkdown(report);
      } else {
        await api.exportReportPdf(report);
      }
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : t("card.downloadFailed"));
    } finally {
      setDownloading(null);
    }
  }

  async function handleRefill() {
    setRefillError(null);
    setRefilling(true);
    try {
      const fresh = await api.refillResearch(report.symbol, report.data_gaps ?? []);
      setReport(fresh);
    } catch (err) {
      setRefillError(err instanceof Error ? err.message : t("card.refillFailed"));
    } finally {
      setRefilling(false);
    }
  }

  return (
    <div
      className={`card light-research-card ${brief ? "light-research-brief" : "light-research-formal"}`}
    >
      <div className="light-research-head">
        <h4>
          {t("card.research")} · {report.name} ({report.symbol})
        </h4>
        <div className="stat-row">
          <span className="stat-pill">
            {t("card.score")} {report.composite_score}/10
            {report.composite_confidence
              ? ` · ${t("card.confidence")} ${localizeConfidence(report.composite_confidence, t)}`
              : ""}
          </span>
          <span className="stat-pill">
            {t("card.bias")} {report.bias}
          </span>
        </div>
      </div>

      <div className="light-research-toolbar">
        {isAdvisor ? (
          <div
            className="light-research-view-toggle"
            role="group"
            aria-label={t("card.reportView")}
          >
            <button
              type="button"
              className={`example-chip ${view === "brief" ? "active" : ""}`}
              onClick={() => setView("brief")}
            >
              {t("card.briefView")}
            </button>
            <button
              type="button"
              className={`example-chip ${view === "formal" ? "active" : ""}`}
              onClick={() => setView("formal")}
            >
              {t("card.formalView")}
            </button>
          </div>
        ) : (
          <span className="muted">{t("card.formalView")}</span>
        )}
        <div className="light-research-download">
          <button
            type="button"
            className="example-chip"
            disabled={downloading != null}
            onClick={() => void handleDownload("md")}
          >
            {downloading === "md" ? t("card.downloading") : t("card.downloadMd")}
          </button>
          <button
            type="button"
            className="example-chip"
            disabled={downloading != null}
            onClick={() => void handleDownload("pdf")}
          >
            {downloading === "pdf" ? t("card.downloading") : t("card.downloadPdf")}
          </button>
          <button
            type="button"
            className="example-chip"
            disabled={downloading != null}
            onClick={() => void handleDownload("json")}
          >
            {downloading === "json" ? t("card.downloading") : t("card.downloadJson")}
          </button>
          <button
            type="button"
            className="example-chip"
            disabled={downloading != null}
            onClick={() => void handleDownload("csv")}
          >
            {downloading === "csv" ? t("card.downloading") : t("card.downloadCsv")}
          </button>
        </div>
      </div>
      {downloadError ? <p className="muted light-research-gaps">{downloadError}</p> : null}
      {brief ? <p className="muted light-research-brief-hint">{t("card.briefHint")}</p> : null}

      <div className="light-research-summary">
        <MarkdownContent text={summaryText} />
      </div>
      <ResearchTrustStrip report={report} compact={brief} onFollowUp={onFollowUp} />
      {dimensions.length > 0 && (
        <DimensionCards
          defaultOpen={isExpert || view === "formal"}
          labels={{
            confidence: t("card.confidence"),
            confidenceHigh: t("card.confidenceHigh"),
            confidenceMedium: t("card.confidenceMedium"),
            confidenceLow: t("card.confidenceLow"),
            highlights: t("card.highlights"),
            risks: t("card.risks"),
            evidence: t("card.evidence"),
            gaps: t("card.missing"),
          }}
          items={dimensionItemsFromResults(
            report.dimensions ?? {},
            (key, agent) => localizeAgentDisplay(key, agent, t),
            { brief },
          )}
        />
      )}
      {(report.deep_analysis?.impact ||
        report.deep_analysis?.pricing ||
        report.deep_analysis?.thesis) &&
        !brief && <DeepAnalysisBlock report={report} compact />}
      {report.data_gaps && report.data_gaps.length > 0 && !brief && (
        <div className="light-research-gaps-row">
          <p className="muted light-research-gaps">
            <strong>{t("card.dataGaps")}：</strong>
            {report.data_gaps.join("；")}
          </p>
          <button
            type="button"
            className="example-chip light-research-refill"
            disabled={refilling}
            onClick={() => void handleRefill()}
            title={t("card.refillGapsTip")}
          >
            {refilling ? t("card.refilling") : t("card.gapCloseRerun")}
          </button>
        </div>
      )}
      {!brief && (
        <div className="light-research-verify-row">
          <HypothesisVerifyButton symbol={report.symbol} name={report.name} />
        </div>
      )}
      {refillError && <p className="error light-research-gaps">{refillError}</p>}
      {followUps.length > 0 && onFollowUp && (
        <div className="follow-up-row">
          {followUps.map((question) => (
            <button
              key={question}
              type="button"
              className="example-chip"
              onClick={() => onFollowUp(question)}
            >
              {question}
            </button>
          ))}
        </div>
      )}
      {!brief && (
        <details className="light-research-details">
          <summary>{isExpert ? t("card.expandSources") : t("card.expandProfessional")}</summary>
          <ResearchReportDetails
            report={report}
            reportId={report.id ?? undefined}
            showDimensions={false}
            showDebate={isExpert}
            showDeepAnalysis={false}
          />
        </details>
      )}
    </div>
  );
}
