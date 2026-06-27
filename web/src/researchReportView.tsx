import type { AshareFactor, DebateResult, DimensionResult, ResearchReport } from "./api";
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

function factorStatusLabel(status: AshareFactor["status"], t: (key: string) => string): string {
  if (status === "verified") return t("card.factorVerified");
  if (status === "partial") return t("card.factorPartial");
  return t("card.factorMissing");
}

function ResearchAshareFactorsBlock({
  factors,
  t,
}: {
  factors?: AshareFactor[];
  t: (key: string) => string;
}) {
  if (!factors?.length) return null;
  return (
    <details className="ashare-factor-block">
      <summary>{t("card.ashareFactors")}</summary>
      <div className="ashare-factor-grid">
        {factors.map((factor) => (
          <article className={`ashare-factor-card ${factor.status}`} key={`${factor.category}-${factor.name}`}>
            <div className="ashare-factor-head">
              <div>
                <span>{factor.category}</span>
                <strong>{factor.name}</strong>
              </div>
              <em>{factorStatusLabel(factor.status, t)}</em>
            </div>
            {factor.evidence.length > 0 && (
              <p>
                <strong>{t("card.evidence")}：</strong>
                {factor.evidence.join("；")}
              </p>
            )}
            {factor.missing.length > 0 && (
              <p className="muted">
                <strong>{t("card.missing")}：</strong>
                {factor.missing.join("；")}
              </p>
            )}
            {factor.source_details?.length > 0 && (
              <div className="ashare-factor-sources" aria-label={t("card.sourceDetails")}>
                {factor.source_details.map((source) => (
                  <span className={`factor-source-pill ${source.status}`} key={source.key} title={source.note || source.key}>
                    {source.layer} · {source.provider} · {source.label}
                  </span>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </details>
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

  const dimEntries = Object.entries(report.dimensions ?? {});
  const allSources = Array.from(
    new Set(dimEntries.flatMap(([, d]) => d.data_sources ?? [])),
  ).filter(Boolean);

  return (
    <div className="research-report-details">
      {allSources.length > 0 && (
        <p className="research-source-hint">
          <span className="muted">{t("card.dataSources")}：</span>
          {allSources.join(" · ")}
        </p>
      )}
      {showDimensions && dimEntries.length > 0 && (
        <details className="research-dimensions-details">
          <summary>{t("card.fourDim")}</summary>
          <ResearchDimensionsBlock dimensions={report.dimensions ?? {}} labels={labels} />
        </details>
      )}
      {showDebate && report.debate && (
        <details className="research-debate-details">
          <summary>{t("card.debateSection")}</summary>
          <ResearchDebateBlock debate={report.debate} labels={debateLabels} />
        </details>
      )}
      <ResearchAshareFactorsBlock factors={report.ashare_factors} t={t} />
      {report.text_factor_summary && (
        <details className="text-factor-block">
          <summary>{t("card.textFactorSummary")}</summary>
          <pre className="text-factor-pre">{report.text_factor_summary}</pre>
        </details>
      )}
    </div>
  );
}

/** 继续追问：研究结论后给出 2–4 个上下文追问，点击直接发起提问。 */
export function FollowUpQuestions({
  report,
  onAsk,
  disabled,
}: {
  report: ResearchReport;
  onAsk: (query: string) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const name = report.name || report.symbol;
  const questions = [
    t("card.followUpTech"),
    t("card.followUpRisk"),
    t("card.followUpCapital"),
    t("card.followUpPeer"),
  ];
  return (
    <div className="follow-up-row">
      <span className="muted follow-up-title">{t("card.followUpTitle")}</span>
      {questions.map((q) => (
        <button
          key={q}
          type="button"
          className="example-chip follow-up-chip"
          disabled={disabled}
          onClick={() => onAsk(`${q}（${name}）`)}
        >
          {q}
        </button>
      ))}
    </div>
  );
}
