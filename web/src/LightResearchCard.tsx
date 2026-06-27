import type { ResearchReport } from "./api";
import { useI18n } from "./i18n";
import type { AppMode } from "./modeSettings";
import { ResearchReportDetails } from "./researchReportView";

const VIEWPOINT_KEYS = ["fundamental", "technical", "sentiment", "chips", "risk"] as const;

interface LightResearchCardProps {
  report: ResearchReport;
  appMode: AppMode;
  onFollowUp?: (query: string) => void;
}

export function LightResearchCard({ report, appMode, onFollowUp }: LightResearchCardProps) {
  const { t } = useI18n();
  const followUps = report.follow_up_questions ?? [];
  const isExpert = appMode === "research";
  const dimensions = Object.entries(report.dimensions ?? {});

  return (
    <div className="card light-research-card">
      <div className="light-research-head">
        <h4>
          {t("card.research")} · {report.name} ({report.symbol})
        </h4>
        <div className="stat-row">
          <span className="stat-pill">
            {t("card.score")} {report.composite_score}/10
          </span>
          <span className="stat-pill">
            {t("card.bias")} {report.bias}
          </span>
        </div>
      </div>
      <p className="light-research-summary">{report.summary}</p>
      {isExpert && dimensions.length > 0 && (
        <div className="light-research-dimensions">
          {dimensions.map(([key, dim]) => (
            <span className="stat-pill" key={key}>
              {dim.agent || key} {dim.score}/10
            </span>
          ))}
        </div>
      )}
      <div className="light-research-viewpoints">
        {VIEWPOINT_KEYS.map((key) => {
          const text = report.viewpoints?.[key];
          if (!text) return null;
          return (
            <div key={key} className="light-viewpoint-row">
              <strong>{t(`card.viewpoint.${key}`)}</strong>
              <span>{text}</span>
            </div>
          );
        })}
      </div>
      {report.data_gaps && report.data_gaps.length > 0 && (
        <p className="muted light-research-gaps">
          <strong>{t("card.dataGaps")}：</strong>
          {report.data_gaps.join("；")}
        </p>
      )}
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
      <details className="light-research-details">
        <summary>{isExpert ? t("card.expandSources") : t("card.expandProfessional")}</summary>
        <ResearchReportDetails
          report={report}
          showDimensions={!isExpert}
          showDebate={isExpert}
        />
      </details>
    </div>
  );
}
