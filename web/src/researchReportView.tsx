import { useState } from "react";
import {
  api,
  type AshareFactor,
  type DebateResult,
  type NumericFactor,
  type ResearchReport,
} from "./api";
import { DeepAnalysisBlock } from "./DeepAnalysisBlock";
import { DimensionCards, dimensionItemsFromResults } from "./DimensionCards";
import { ResearchTrustStrip } from "./ResearchTrustStrip";
import { useI18n } from "./i18n";
import { EVENT_KEYS, recordEvent } from "./usageTracking";
import { loadModeSettings } from "./modeSettings";
import { localizeAgentDisplay } from "./uiLabels";

function biasLabel(bias: string, t: (key: string) => string): string {
  const key = `card.${bias}` as const;
  const translated = t(key);
  return translated !== key ? translated : bias;
}

// 纯函数导出供 ChatPanel/replyCardDedup 复用；与组件同文件仅影响 HMR 精确度
// eslint-disable-next-line react-refresh/only-export-components
export function findResearchReport(
  cards?: { type: string; data: Record<string, unknown> }[],
): ResearchReport | null {
  const card = cards?.find((c) => c.type === "research" && c.data && "composite_score" in c.data);
  return card ? (card.data as unknown as ResearchReport) : null;
}

// eslint-disable-next-line react-refresh/only-export-components
export function hasDebateStream(process?: {
  debateRounds: unknown[];
  judgeVerdict: unknown;
}): boolean {
  if (!process) return false;
  return process.debateRounds.length > 0 || process.judgeVerdict != null;
}

// eslint-disable-next-line react-refresh/only-export-components
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
  return process.agentSteps.some((s) => ids.has(s.agent_id) && s.status !== "pending");
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

function isNewsTextFactor(factor: AshareFactor): boolean {
  return factor.name.includes("新闻") || factor.category.includes("新闻");
}

function ResearchAshareFactorsBlock({
  factors,
  t,
}: {
  factors?: AshareFactor[];
  t: (key: string) => string;
}) {
  const visible = factors?.filter((factor) => !isNewsTextFactor(factor)) ?? [];
  if (!visible.length) return null;
  return (
    <details className="ashare-factor-block">
      <summary>{t("card.ashareFactors")}</summary>
      <div className="ashare-factor-grid">
        {visible.map((factor) => (
          <article
            className={`ashare-factor-card ${factor.status}`}
            key={`${factor.category}-${factor.name}`}
          >
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
                  <span
                    className={`factor-source-pill ${source.status}`}
                    key={source.key}
                    title={source.note || source.key}
                  >
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

function ResearchNumericFactorsBlock({
  factors,
  expanded = false,
  alignmentNote,
  t,
}: {
  factors?: NumericFactor[];
  expanded?: boolean;
  alignmentNote?: string | null;
  t: (key: string) => string;
}) {
  if (!factors?.length) return null;
  return (
    <details className="ashare-factor-block" open={expanded || undefined}>
      <summary>{t("card.numericFactors")}</summary>
      {alignmentNote ? <p className="muted">{alignmentNote}</p> : null}
      <div className="ashare-factor-grid">
        {factors.map((factor) => (
          <article
            className={`ashare-factor-card ${factor.partial ? "partial" : "verified"}`}
            key={factor.key}
          >
            <div className="ashare-factor-head">
              <div>
                <span>{factor.key}</span>
                <strong>{factor.label}</strong>
              </div>
              <em>{factor.partial ? t("card.factorPartial") : t("card.factorVerified")}</em>
            </div>
            <p>
              {factor.value != null ? `${factor.value}${factor.unit || ""}` : "—"}
              {factor.percentile != null ? ` · P${Math.round(factor.percentile * 100)}` : ""}
              {factor.as_of ? ` · ${factor.as_of}` : ""}
            </p>
            {factor.note ? <p className="muted">{factor.note}</p> : null}
          </article>
        ))}
      </div>
    </details>
  );
}

export function ResearchReportDetails({
  report,
  reportId,
  showDimensions = true,
  showDebate = true,
  showDeepAnalysis = true,
}: {
  report: ResearchReport;
  reportId?: number;
  showDimensions?: boolean;
  showDebate?: boolean;
  showDeepAnalysis?: boolean;
}) {
  const { t } = useI18n();
  const settings = loadModeSettings();
  const [viewMode, setViewMode] = useState<"professional" | "plain">("professional");
  const [plainReport, setPlainReport] = useState<ResearchReport | null>(null);
  const [plainLoading, setPlainLoading] = useState(false);
  const [plainNotice, setPlainNotice] = useState<string | null>(null);

  const displayReport = viewMode === "plain" && plainReport ? plainReport : report;
  const dimEntries = Object.entries(displayReport.dimensions ?? {});
  const allSources = Array.from(
    new Set(dimEntries.flatMap(([, d]) => d.data_sources ?? [])),
  ).filter(Boolean);
  const evidenceOpen = settings.mode === "research";

  const switchToPlain = async () => {
    if (!reportId || plainReport) {
      if (plainReport) setViewMode("plain");
      return;
    }
    setPlainLoading(true);
    setPlainNotice(null);
    try {
      const out = await api.plainReport(reportId);
      if (out.source === "degraded") {
        setPlainNotice(out.message ?? t("card.plainDegraded"));
      } else {
        setPlainReport(out.report);
        setViewMode("plain");
      }
    } catch {
      setPlainNotice(t("card.plainDegraded"));
    } finally {
      setPlainLoading(false);
    }
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
      {reportId && (
        <div className="report-tone-switch">
          <span className="report-tone-label">{t("card.toneLabel")}</span>
          <div className="tone-toggle" role="group" aria-label={t("card.toneLabel")}>
            <button
              type="button"
              className={viewMode === "professional" ? "active" : ""}
              onClick={() => {
                setViewMode("professional");
                setPlainNotice(null);
              }}
              disabled={plainLoading}
            >
              {t("card.viewProfessional")}
            </button>
            <button
              type="button"
              className={viewMode === "plain" ? "active" : ""}
              onClick={switchToPlain}
              disabled={plainLoading}
            >
              {plainLoading ? t("card.plainLoading") : t("card.viewPlain")}
            </button>
          </div>
          {plainNotice && <p className="report-tone-notice">{plainNotice}</p>}
        </div>
      )}
      <ResearchTrustStrip report={displayReport} />
      {allSources.length > 0 && (
        <p className="research-source-hint">
          <span className="muted">{t("card.dataSources")}：</span>
          {allSources.join(" · ")}
        </p>
      )}
      {(displayReport.data_gaps?.length ?? 0) > 0 && (
        <p className="research-source-hint muted">
          <span>{t("card.dataGaps")}：</span>
          {displayReport.data_gaps!.join("；")}
        </p>
      )}
      {showDimensions && dimEntries.length > 0 && (
        <DimensionCards
          defaultOpen={evidenceOpen}
          labels={{
            confidence: t("card.confidence"),
            confidenceHigh: t("card.confidenceHigh"),
            confidenceMedium: t("card.confidenceMedium"),
            confidenceLow: t("card.confidenceLow"),
            highlights: t("card.highlights"),
            risks: t("card.risks"),
            evidence: t("card.evidence"),
            gaps: t("card.missing"),
            partial: t("card.factorPartial"),
          }}
          items={dimensionItemsFromResults(displayReport.dimensions ?? {}, (key, agent) =>
            localizeAgentDisplay(key, agent, t),
          )}
        />
      )}
      {showDeepAnalysis &&
        (displayReport.deep_analysis?.impact ||
          displayReport.deep_analysis?.pricing ||
          displayReport.deep_analysis?.thesis) && <DeepAnalysisBlock report={displayReport} />}
      {showDebate && displayReport.debate && (
        <details
          className="research-debate-details"
          onToggle={() => recordEvent(EVENT_KEYS.debateExpand)}
        >
          <summary>{t("card.debateSection")}</summary>
          <ResearchDebateBlock debate={displayReport.debate} labels={debateLabels} />
        </details>
      )}
      <ResearchNumericFactorsBlock
        factors={displayReport.factors}
        expanded={false}
        alignmentNote={displayReport.factor_alignment_note}
        t={t}
      />
      <ResearchAshareFactorsBlock factors={displayReport.ashare_factors} t={t} />
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
