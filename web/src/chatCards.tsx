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
import { localizeDebateAgentName, localizeRating } from "./uiLabels";
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

export function CardView({ card }: { card: ChatResponse["cards"][0] }) {
  const { t } = useI18n();
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
          <p>
            {normalizeResearchConclusion(d.summary, {
              expandHints: researchExpandHintsFromReport(d),
            })}
          </p>
          {/^\d{6}$/.test(d.symbol) && <StockChart symbol={d.symbol} compact />}
        </div>
      );
    }
    if (card.type === "risk" && card.data && "portfolio_summary" in card.data) {
      const d = card.data as unknown as RiskCheckup;
      return (
        <div className="card">
          <h4>{t("card.riskCheckup")}</h4>
          <p>{d.portfolio_summary}</p>
          {d.alerts?.slice(0, 3).map((a, i) => (
            <p key={i} className={`alert-${a.severity}`}>
              {a.human_message}
            </p>
          ))}
          {d.llm_analysis && (
            <p>
              <strong>{t("card.aiBrief")}:</strong> {d.llm_analysis.risk_narrative}
            </p>
          )}
        </div>
      );
    }
    if (card.type === "news" && card.data && "items" in card.data) {
      const items = (card.data as { items: NewsItem[] }).items || [];
      return (
        <div className="card">
          <h4>{t("card.relatedNews")}</h4>
          {items.slice(0, 3).map((n, i) => (
            <p key={i}>
              {n.title} — {n.summary}
            </p>
          ))}
        </div>
      );
    }
    if (card.type === "debate" && card.data && "positions" in card.data) {
      const d = card.data as {
        positions: { agent: string; stance: string; arguments: string }[];
        vote_tally: Record<string, number>;
        final_bias: string;
        synthesis: string;
        symbol: string;
        name: string;
      };
      const biasLabel: Record<string, string> = {
        bullish: t("card.bullish"),
        bearish: t("card.bearish"),
        neutral: t("card.neutral"),
      };
      const stanceColor: Record<string, string> = {
        看多: "up",
        看空: "down",
        中性: "",
        Long: "up",
        Short: "down",
        Neutral: "",
        bullish: "up",
        bearish: "down",
      };
      const stanceLabel = (s: string) =>
        ({ 看多: t("card.long"), 看空: t("card.short"), 中性: t("card.neutral"), Long: t("card.long"), Short: t("card.short"), Neutral: t("card.neutral"), bullish: t("card.long"), bearish: t("card.short") } as Record<string, string>)[s] ?? s;
      return (
        <div className="card">
          <h4>
            {t("card.debate")} · {d.name}({d.symbol})
          </h4>
          <div className="stat-row">
            <span className="stat-pill">
              {t("card.long")} {(d.vote_tally["看多"] || d.vote_tally["Long"] || d.vote_tally["bullish"] || 0)}
            </span>
            <span className="stat-pill">
              {t("card.short")} {(d.vote_tally["看空"] || d.vote_tally["Short"] || d.vote_tally["bearish"] || 0)}
            </span>
            <span className="stat-pill">
              {t("card.neutral")} {(d.vote_tally["中性"] || d.vote_tally["Neutral"] || d.vote_tally["neutral"] || 0)}
            </span>
            <span
              className={`stat-pill ${d.final_bias === "bullish" ? "up" : d.final_bias === "bearish" ? "down" : ""}`}
            >
              {t("card.bias")} {biasLabel[d.final_bias] || d.final_bias}
            </span>
          </div>
          {d.positions.map((p, i) => (
            <div key={i} className={`debate-position ${stanceColor[p.stance] || ""}`}>
              <strong>
                {localizeDebateAgentName(p.agent, t)}
              </strong>{" "}
              <span className={`stat-pill ${stanceColor[p.stance]}`}>{stanceLabel(p.stance)}</span>
              <p className="muted" style={{ marginTop: 2 }}>
                {p.arguments.slice(0, 200)}
                {p.arguments.length > 200 ? "..." : ""}
              </p>
            </div>
          ))}
          {d.synthesis && (
            <div style={{ marginTop: 8, borderTop: "1px solid var(--bbg-border)", paddingTop: 8 }}>
              <strong>{t("card.judge")}</strong>
              <div style={{ marginTop: 4 }}>
                <MarkdownContent text={d.synthesis} />
              </div>
            </div>
          )}
        </div>
      );
    }
    if (card.type === "financial" && card.data && "ratios" in card.data) {
      const d = card.data as {
        symbol: string;
        name: string;
        ratios: { name: string; value: string; reference: string; assessment: string }[];
        summary: string;
      };
      return (
        <div className="card">
          <h4>
            {t("card.financial")} · {d.name}({d.symbol})
          </h4>
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
      );
    }
    if (card.type === "plan" && card.data) {
      const d = card.data as {
        phase: string;
        reasoning?: string;
        steps?: { id: number; description: string }[];
        step_id?: number;
        step?: string;
        result_preview?: string;
      };
      if (d.phase === "plan") {
        return (
          <div className="card">
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
          <div className="card" style={{ borderLeft: "2px solid var(--bbg-amber)" }}>
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
          <div className="card" style={{ borderLeft: "2px solid var(--bbg-green, #3d9970)" }}>
            <h4>{t("card.synthesis")}</h4>
            <p className="muted">
              {t("card.synthesisHint", {
                count: String((d as { step_count?: number }).step_count ?? ""),
              })}
            </p>
          </div>
        );
      }
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
