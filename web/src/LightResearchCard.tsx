import type { ResearchReport } from "./api";
import { DimensionCards, dimensionItemsFromResults } from "./DimensionCards";
import { useI18n } from "./i18n";
import type { AppMode } from "./modeSettings";
import { MarkdownContent } from "./MarkdownContent";
import { normalizeResearchConclusion, researchExpandHintsFromReport } from "./researchText";
import { ResearchReportDetails } from "./researchReportView";
import { localizeAgentDisplay } from "./uiLabels";

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
      <div className="light-research-summary">
        <MarkdownContent
          text={normalizeResearchConclusion(report.summary, {
            expandHints: researchExpandHintsFromReport(report),
          })}
        />
      </div>
      {dimensions.length > 0 && (
        <DimensionCards
          defaultOpen={false}
          labels={{
            confidence: t("card.confidence"),
            highlights: t("card.highlights"),
            risks: t("card.risks"),
          }}
          items={dimensionItemsFromResults(report.dimensions ?? {}, (key, agent) =>
            localizeAgentDisplay(key, agent, t),
          )}
        />
      )}
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
      {report.master_commentary && report.master_commentary.length > 0 && (
        <div className="master-commentary-list light-research-masters">
          <p className="stream-section-title">{t("stream.masterCommentary")}</p>
          {report.master_commentary.map((item) => {
            const label =
              item.name?.trim() ||
              (() => {
                const key = `master.${item.master}`;
                const translated = t(key);
                return translated !== key ? translated : item.master;
              })();
            return (
              <div
                key={item.master}
                className={`master-commentary-item signal-${item.signal}`}
              >
                <div className="master-commentary-head">
                  <strong>{label}</strong>
                  <span
                    className={`stat-pill ${item.signal === "bullish" ? "up" : item.signal === "bearish" ? "down" : ""}`}
                  >
                    {item.signal_text}
                  </span>
                  {item.key_metric && (
                    <span className="muted master-commentary-metric">{item.key_metric}</span>
                  )}
                </div>
                <p className="muted">{item.reasoning}</p>
              </div>
            );
          })}
        </div>
      )}
      <details className="light-research-details">
        <summary>{isExpert ? t("card.expandSources") : t("card.expandProfessional")}</summary>
        <ResearchReportDetails report={report} showDimensions={false} showDebate={isExpert} />
      </details>
    </div>
  );
}
