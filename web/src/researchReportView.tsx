import type { DebateResult, DimensionResult, ResearchReport } from "./api";
import { useI18n } from "./i18n";

function biasLabel(bias: string, t: (key: string) => string): string {
  const key = `card.${bias}` as const;
  const translated = t(key);
  return translated !== key ? translated : bias;
}

export function findResearchReport(
  cards?: { type: string; data: Record<string, unknown> }[],
): ResearchReport | null {
  const card = cards?.find(
    (c) => c.type === "research" && c.data && "composite_score" in c.data,
  );
  return card ? (card.data as unknown as ResearchReport) : null;
}

export function hasDebateStream(process?: {
  debateRounds: unknown[];
  judgeVerdict: unknown;
}): boolean {
  if (!process) return false;
  return process.debateRounds.length > 0 || process.judgeVerdict != null;
}

export function hasDimensionStream(process?: {
  agentSteps: { agent_id: string; status: string }[];
}): boolean {
  if (!process) return false;
  const ids = new Set([
    "fundamental",
    "technical",
    "sentiment",
    "chips",
    "macro",
    "industry",
    "policy",
    "capital",
    "valuation",
    "structure",
  ]);
  return process.agentSteps.some(
    (s) => ids.has(s.agent_id) && s.status !== "pending",
  );
}

function ResearchDimensionsBlock({
  dimensions,
  labels,
}: {
  dimensions: Record<string, DimensionResult>;
  labels: {
    section: string;
    confidence: string;
    highlights: string;
    risks: string;
  };
}) {
  const entries = Object.entries(dimensions);
  if (!entries.length) return null;
  return (
    <div className="research-dimensions">
      <p className="stream-section-title">{labels.section}</p>
      {entries.map(([key, dim]) => (
        <div key={key} className="dimension-card dimension-done research-dim-card">
          <div className="dimension-card-head">
            <strong>{dim.agent || key}</strong>
            <span className="stat-pill">
              {dim.score}/10 · {labels.confidence} {dim.confidence}
            </span>
          </div>
          <div className="dimension-card-body">
            {dim.highlights?.length > 0 && (
              <p>
                <strong>{labels.highlights}：</strong>
                {dim.highlights.join("；")}
              </p>
            )}
            {dim.risks?.length > 0 && (
              <p className="muted">
                <strong>{labels.risks}：</strong>
                {dim.risks.join("；")}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function ResearchDebateBlock({
  debate,
  labels,
}: {
  debate: DebateResult;
  labels: {
    section: string;
    long: string;
    short: string;
    judge: string;
    manager: string;
    round: (n: number) => string;
    voteTally: (bull: number, bear: number, neutral: number) => string;
    bias: (value: string) => string;
  };
}) {
  if (!debate.rounds?.length && !debate.consensus) return null;
  return (
    <div className="research-debate">
      <p className="stream-section-title">{labels.section}</p>
      {debate.rounds?.map((rnd) => (
        <div key={rnd.round} className="debate-grid">
          {rnd.bull_argument && (
            <div className="debate-bull">
              <strong>
                {labels.round(rnd.round)} · {labels.long}
              </strong>
              <p>{rnd.bull_argument}</p>
            </div>
          )}
          {rnd.bear_rebuttal && (
            <div className="debate-bear">
              <strong>
                {labels.round(rnd.round)} · {labels.short}
              </strong>
              <p>{rnd.bear_rebuttal}</p>
            </div>
          )}
        </div>
      ))}
      {debate.vote_tally && (
        <p className="muted">
          {labels.voteTally(
            debate.vote_tally["偏多"] ?? 0,
            debate.vote_tally["偏空"] ?? 0,
            debate.vote_tally["中性"] ?? 0,
          )}
        </p>
      )}
      {debate.manager_thesis && (
        <div className="debate-judge">
          <strong>{labels.manager}</strong>
          <p>{debate.manager_thesis}</p>
        </div>
      )}
      {(debate.consensus || debate.judge_verdict) && (
        <div className="debate-judge">
          <strong>
            {labels.judge}
            {debate.final_bias ? ` · ${labels.bias(debate.final_bias)}` : ""}
          </strong>
          <p>{debate.consensus || debate.judge_verdict}</p>
          {debate.core_divergence && <p className="muted">{debate.core_divergence}</p>}
        </div>
      )}
    </div>
  );
}

export function ResearchReportDetails({
  report,
  showDimensions = true,
  showDebate = true,
}: {
  report: ResearchReport;
  showDimensions?: boolean;
  showDebate?: boolean;
}) {
  const { t } = useI18n();
  const labels = {
    section: t("card.fourDim"),
    confidence: t("card.confidence"),
    highlights: t("card.highlights"),
    risks: t("card.risks"),
  };
  const debateLabels = {
    section: t("card.debateSection"),
    long: t("card.long"),
    short: t("card.short"),
    judge: t("card.judge"),
    manager: t("card.managerThesis"),
    round: (n: number) => t("card.round", { n: String(n) }),
    voteTally: (bull: number, bear: number, neutral: number) =>
      t("card.voteTally", {
        bull: String(bull),
        bear: String(bear),
        neutral: String(neutral),
      }),
    bias: (value: string) => biasLabel(value, t),
  };

  return (
    <div className="research-report-details">
      {showDimensions && (
        <ResearchDimensionsBlock dimensions={report.dimensions ?? {}} labels={labels} />
      )}
      {showDebate && report.debate && (
        <ResearchDebateBlock debate={report.debate} labels={debateLabels} />
      )}
      {report.text_factor_summary && (
        <details className="text-factor-block">
          <summary>{t("card.textFactorSummary")}</summary>
          <pre className="text-factor-pre">{report.text_factor_summary}</pre>
        </details>
      )}
    </div>
  );
}
