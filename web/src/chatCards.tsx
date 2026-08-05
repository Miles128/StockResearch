import { useState } from "react";
import type {
  ChatResponse,
  ExecutionPreference,
  NewsItem,
  ResearchReport,
  RiskCheckup,
  RouteChoiceCardData,
  StockChoiceCardData,
} from "./api";
import { useI18n } from "./i18n";
import { translateRouteOption, translateRouteReason } from "./streamI18n";
import { localizeRating } from "./uiLabels";
import { MarkdownContent } from "./MarkdownContent";
import { normalizeResearchConclusion, researchExpandHintsFromReport } from "./researchText";
import { StockChart } from "./StockChart";

export function RouteChoiceCardView({
  data,
  disabled,
  onConfirm,
}: {
  data: RouteChoiceCardData;
  disabled: boolean;
  onConfirm: (originalMessage: string, preference: ExecutionPreference) => void;
}) {
  const { t } = useI18n();
  const [picked, setPicked] = useState(false);
  return (
    <div className="confirm-card message assistant">
      <p className="process-panel-title">{t("chat.chooseRoute")}</p>
      <p className="muted">{translateRouteReason(data, t)}</p>
      <div className="candidate-list route-choice-list">
        {data.options.map((opt) => {
          const { label, description } = translateRouteOption(opt, t);
          return (
            <button
              key={opt.id}
              type="button"
              className="btn btn-ghost route-choice-btn"
              disabled={disabled || picked}
              onClick={() => {
                setPicked(true);
                onConfirm(data.original_message, opt.id);
              }}
            >
              <span className="route-choice-label">{label}</span>
              <span className="route-choice-desc muted">{description}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function StockChoiceCardView({
  data,
  disabled,
  onConfirm,
}: {
  data: StockChoiceCardData;
  disabled: boolean;
  onConfirm: (originalMessage: string, symbol: string, name: string) => void;
}) {
  const { t } = useI18n();
  const [picked, setPicked] = useState(false);
  return (
    <div className="confirm-card message assistant">
      <p className="process-panel-title">{t("chat.pickStock")}</p>
      <p className="muted">{data.message}</p>
      {data.candidates.length > 0 && (
        <div className="candidate-list">
          {data.candidates.map((c) => (
            <button
              key={c.symbol}
              type="button"
              className="btn btn-ghost"
              disabled={disabled || picked}
              onClick={() => {
                setPicked(true);
                onConfirm(data.original_message, c.symbol, c.name);
              }}
            >
              {c.name} ({c.symbol})
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function PlanCardsFold({ cards }: { cards: ChatResponse["cards"] }) {
  const { t } = useI18n();
  const planCards = cards.filter((c) => c.type === "plan");
  if (!planCards.length) return null;
  return (
    <details className="process-trail-fold plan-trail-fold">
      <summary className="process-trail-summary">{t("card.planTrail")}</summary>
      <div className="process-trail-body">
        {planCards.map((card, i) => (
          <PlanCardItem key={i} card={card} />
        ))}
      </div>
    </details>
  );
}

function PlanCardItem({ card }: { card: ChatResponse["cards"][0] }) {
  const { t } = useI18n();
  if (card.type !== "plan" || !card.data) return null;
  const d = card.data as {
    phase: string;
    reasoning?: string;
    steps?: { id: number; description: string }[];
    step_id?: number;
    step?: string;
    result_preview?: string;
    step_count?: number;
  };
  if (d.phase === "plan") {
    return (
      <div className="card plan-step-card">
        <h4>{t("card.plan")}</h4>
        {d.reasoning && <p className="muted">{d.reasoning}</p>}
        <ol style={{ margin: "4px 0", paddingLeft: 20 }}>
          {d.steps?.map((s, i) => (
            <li key={i}>{s.description}</li>
          ))}
        </ol>
      </div>
    );
  }
  if (d.phase === "execute") {
    return (
      <div className="card plan-step-card plan-step-execute">
        <h4>
          {t("card.step")} {d.step_id}
        </h4>
        <p className="muted">{d.step}</p>
        {d.result_preview && <p style={{ marginTop: 4 }}>{d.result_preview}</p>}
      </div>
    );
  }
  if (d.phase === "synthesis") {
    return (
      <div className="card plan-step-card plan-step-synthesis">
        <h4>{t("card.synthesis")}</h4>
        <p className="muted">
          {t("card.synthesisHint", {
            count: String(d.step_count ?? ""),
          })}
        </p>
      </div>
    );
  }
  return null;
}

export function CardView({ card }: { card: ChatResponse["cards"][0] }) {
  const { t } = useI18n();
  if (card.type === "plan") {
    return null;
  }
  if (card.type === "research" && card.data && "composite_score" in card.data) {
    const d = card.data as unknown as ResearchReport;
    return (
      <div className="card">
        <h4>
          {t("card.research")} · {d.name} ({d.symbol})
        </h4>
        <div className="stat-row">
          <span className="stat-pill">
            {t("card.score")} {d.composite_score}/10
          </span>
          <span className="stat-pill">
            {t("card.bias")} {d.bias}
          </span>
        </div>
        <div className="light-research-summary">
          <MarkdownContent
            text={normalizeResearchConclusion(d.summary, {
              expandHints: researchExpandHintsFromReport(d),
            })}
          />
        </div>
        {/^\d{6}$/.test(d.symbol) && <StockChart key={d.symbol} symbol={d.symbol} compact />}
      </div>
    );
  }
  if (card.type === "risk" && card.data && "portfolio_summary" in card.data) {
    const d = card.data as unknown as RiskCheckup;
    return (
      <div className="card">
        <h4>{t("card.riskCheckup")}</h4>
        <MarkdownContent text={d.portfolio_summary} />
        {d.alerts?.slice(0, 3).map((a, i) => (
          <p key={i} className={`alert-${a.severity}`}>
            {a.human_message}
          </p>
        ))}
        {d.llm_analysis && (
          <div>
            <strong>{t("card.aiBrief")}:</strong>{" "}
            <MarkdownContent className="markdown-inline" text={d.llm_analysis.risk_narrative} />
          </div>
        )}
      </div>
    );
  }
  if (card.type === "news" && card.data && "items" in card.data) {
    const items = (card.data as { items: NewsItem[] }).items || [];
    if (!items.length) return null;
    return (
      <details className="card news-card-fold">
        <summary className="news-card-summary">
          {t("card.relatedNews")} ({items.length})
        </summary>
        <div className="news-card-body">
          {items.slice(0, 5).map((n, i) => (
            <p key={i}>
              <strong>{n.title}</strong>
              {n.summary ? ` — ${n.summary}` : ""}
            </p>
          ))}
        </div>
      </details>
    );
  }
  if (card.type === "financial" && card.data && "ratios" in card.data) {
    const d = card.data as {
      symbol: string;
      name: string;
      ratios: {
        name: string;
        value: string;
        reference: string;
        assessment: string;
      }[];
      summary: string;
    };
    return (
      <details className="card financial-card-fold">
        <summary className="news-card-summary">
          {t("card.financial")} · {d.name}({d.symbol})
        </summary>
        <div className="news-card-body">
          <table className="metrics-table">
            <thead>
              <tr>
                <th>{t("card.metric")}</th>
                <th>{t("card.value")}</th>
                <th>{t("card.benchmark")}</th>
                <th>{t("card.assessment")}</th>
              </tr>
            </thead>
            <tbody>
              {d.ratios.map((r, i) => (
                <tr key={i}>
                  <td>{r.name}</td>
                  <td className="mono">{r.value}</td>
                  <td className="muted">{r.reference}</td>
                  <td
                    className={
                      r.assessment.includes("高") || r.assessment.includes("过")
                        ? "down"
                        : r.assessment.includes("优") || r.assessment.includes("良")
                          ? "up"
                          : ""
                    }
                  >
                    {localizeRating(r.assessment, t)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {d.summary && (
            <div style={{ marginTop: 8 }}>
              <MarkdownContent text={d.summary} />
            </div>
          )}
        </div>
      </details>
    );
  }
  if (card.type === "text" && card.data && "content" in card.data) {
    const content = String((card.data as { content: string }).content || "");
    if (!content) return null;
    return (
      <div className="card">
        <MarkdownContent text={content} />
      </div>
    );
  }
  return null;
}
