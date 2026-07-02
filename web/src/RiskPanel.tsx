import { useState, type ReactNode } from "react";
import type { HoldingEnriched, RiskCheckup } from "./api";
import { CollapsibleSection } from "./CollapsibleSection";
import { MarkdownContent } from "./MarkdownContent";
import { RiskSourceCharts } from "./RiskSourceCharts";
import { StreamFeed } from "./StreamFeed";
import { useI18n } from "./i18n";
import { hasLiveProcessContent, type StreamState } from "./streamEvents";
import { IconAlert, IconBolt, IconChart } from "./ui/Icons";
import { localizeRiskRuleId, localizeSeverity } from "./uiLabels";

interface RiskPanelProps {
  holdings: HoldingEnriched[];
  risk: RiskCheckup | null;
  loading: boolean;
  riskStream: StreamState;
  riskStatusMsg: string;
  numLocale: string;
  ratioGrade: (v: number, excellent: number, good: number) => string;
  alertHoldingTags: (message: string) => HoldingEnriched[];
  onRunRisk: () => void;
  onGoPortfolio: () => void;
  onAskCopilot?: (query: string) => void;
}

function riskLevelColor(alertCount: number): string {
  if (alertCount === 0) return "green";
  if (alertCount <= 2) return "yellow";
  return "red";
}

function riskLevelLabel(alertCount: number, t: (k: string) => string): string {
  if (alertCount === 0) return t("risk.levelLow");
  if (alertCount <= 2) return t("risk.levelMedium");
  return t("risk.levelHigh");
}

function alertOneLine(message: string): string {
  const trimmed = message.trim();
  const match = trimmed.match(/^[^。！？\n]+[。！？]?/);
  if (!match) return trimmed;
  const line = match[0].trim();
  return line.length < trimmed.length ? line : trimmed;
}

function metricBarWidth(pct: number): number {
  return Math.min(Math.abs(pct) * 100 * 2, 100);
}

function RiskMetricGauge({
  label,
  valueText,
  pctText,
  pct,
  tone = "var",
  icon,
}: {
  label: string;
  valueText: string;
  pctText: string;
  pct: number;
  tone?: "var" | "el";
  icon: ReactNode;
}) {
  return (
    <div className={`risk-metric-gauge risk-metric-gauge-${tone}`}>
      <div className="risk-metric-gauge-head">
        <span className="risk-metric-gauge-icon">{icon}</span>
        <span className="risk-metric-gauge-label">{label}</span>
      </div>
      <div className="risk-metric-gauge-value">{valueText}</div>
      <div className="risk-metric-gauge-pct">{pctText}</div>
      <div className="risk-metric-gauge-track">
        <div className="risk-metric-gauge-fill" style={{ width: `${metricBarWidth(pct)}%` }} />
      </div>
    </div>
  );
}

export function RiskPanel({
  holdings,
  risk,
  loading,
  riskStream,
  riskStatusMsg,
  numLocale,
  ratioGrade,
  alertHoldingTags,
  onRunRisk,
  onGoPortfolio,
  onAskCopilot,
}: RiskPanelProps) {
  const { t } = useI18n();
  const [metricsExpanded, setMetricsExpanded] = useState(false);
  const [agentFoldOpen, setAgentFoldOpen] = useState(false);
  const showProcess = loading || hasLiveProcessContent(riskStream);

  const alertCount = risk?.alerts.length ?? 0;
  const hasQuantData = Boolean(risk?.var_result || risk?.metrics);
  const hasCharts = Boolean(risk && holdings.length > 0);

  return (
    <div className="panel risk-panel">
      <div className="risk-panel-head">
        <div className="risk-panel-title-row">
          <IconAlert className="ui-icon risk-panel-icon" size={18} />
          <h2 className="risk-panel-title">{t("center.risk")}</h2>
          {risk && (
            <span className={`risk-level-pill risk-level-${riskLevelColor(alertCount)}`}>
              {riskLevelLabel(alertCount, t)}
            </span>
          )}
        </div>
        {holdings.length > 0 && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={onRunRisk} disabled={loading}>
            {loading ? t("risk.running") : t("risk.refresh")}
          </button>
        )}
      </div>

      {onAskCopilot && holdings.length > 0 && (
        <div className="ai-action-row">
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => onAskCopilot(t("risk.askTopRisk"))}>
            {t("risk.askTopRisk")}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => onAskCopilot(t("risk.askStress"))}>
            {t("risk.askStress")}
          </button>
        </div>
      )}

      {holdings.length === 0 ? (
        <div className="risk-empty-cta">
          <p className="muted">{t("risk.emptyHoldings")}</p>
          <button type="button" className="btn btn-primary" onClick={onGoPortfolio}>
            {t("risk.goPortfolio")}
          </button>
        </div>
      ) : (
        <>
          {loading && !risk && riskStatusMsg && !showProcess && (
            <p className="risk-status-line muted">{riskStatusMsg}</p>
          )}

          {hasCharts && (
            <>
              <RiskSourceCharts risk={risk!} holdings={holdings} numLocale={numLocale} />

              {hasQuantData && (
                <section className="risk-metrics-top">
                  <button
                    type="button"
                    className={`risk-metrics-cards${metricsExpanded ? " expanded" : ""}`}
                    onClick={() => setMetricsExpanded((v) => !v)}
                    aria-expanded={metricsExpanded}
                  >
                    {risk!.var_result && (
                      <RiskMetricGauge
                        label={t("risk.var")}
                        valueText={`¥${risk!.var_result.var_value.toLocaleString(numLocale, {
                          minimumFractionDigits: 0,
                          maximumFractionDigits: 0,
                        })}`}
                        pctText={`${(risk!.var_result.var_pct * 100).toFixed(2)}% · ${t("risk.varHuman", {
                          days: String(risk!.var_result.time_horizon_days),
                          conf: String(Math.round(risk!.var_result.confidence_level * 100)),
                        })}`}
                        pct={risk!.var_result.var_pct}
                        tone="var"
                        icon={<IconChart size={16} />}
                      />
                    )}
                    {risk!.metrics && (
                      <RiskMetricGauge
                        label={t("risk.expectedLoss")}
                        valueText={`¥${risk!.metrics.expected_loss.toLocaleString(numLocale, {
                          minimumFractionDigits: 0,
                          maximumFractionDigits: 0,
                        })}`}
                        pctText={`${(risk!.metrics.expected_loss_pct * 100).toFixed(2)}% · PD×LGD×EAD`}
                        pct={risk!.metrics.expected_loss_pct}
                        tone="el"
                        icon={<IconBolt size={16} />}
                      />
                    )}
                    <span className="risk-metrics-expand-hint muted">
                      {metricsExpanded ? t("risk.collapseMetrics") : t("risk.expandMetrics")}
                    </span>
                  </button>

                  {metricsExpanded && (
                    <div className="risk-metrics-detail">
                      {risk!.var_result && (
                        <CollapsibleSection title={t("risk.varBreakdown")} defaultCollapsed={false}>
                          <div className="stat-row">
                            <span className="stat-pill">
                              {t("risk.confidence")} {(risk!.var_result.confidence_level * 100).toFixed(0)}%
                            </span>
                            <span className="stat-pill">
                              {t("risk.horizon")} {risk!.var_result.time_horizon_days}
                              {t("risk.days")}
                            </span>
                            <span className="stat-pill">
                              {t("risk.method")} {risk!.var_result.method}
                            </span>
                          </div>
                          <div className="var-display">
                            <div className="var-main">
                              <span className="var-label">{t("risk.varAbs")}</span>
                              <span className="var-value down">
                                ¥
                                {risk!.var_result.var_value.toLocaleString(numLocale, {
                                  minimumFractionDigits: 2,
                                })}
                              </span>
                            </div>
                            <div className="var-main">
                              <span className="var-label">{t("risk.cvar")}</span>
                              <span className="var-value down">
                                ¥
                                {risk!.var_result.cvar_value.toLocaleString(numLocale, {
                                  minimumFractionDigits: 2,
                                })}
                              </span>
                            </div>
                          </div>
                          {risk!.var_result.holdings_var.length > 0 && (
                            <table className="metrics-table">
                              <thead>
                                <tr>
                                  <th>{t("risk.stock")}</th>
                                  <th>{t("risk.weight")}</th>
                                  <th>VaR</th>
                                </tr>
                              </thead>
                              <tbody>
                                {risk!.var_result.holdings_var.map((h, i) => (
                                  <tr key={i}>
                                    <td>{h.name}</td>
                                    <td className="mono">{((h.weight ?? 0) * 100).toFixed(1)}%</td>
                                    <td className="mono down">
                                      ¥
                                      {(h.var_value ?? 0).toLocaleString(numLocale, {
                                        minimumFractionDigits: 2,
                                      })}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </CollapsibleSection>
                      )}

                      {risk!.metrics && (
                        <CollapsibleSection title={t("risk.metrics")} defaultCollapsed={false}>
                          <table className="metrics-table">
                            <tbody>
                              <tr>
                                <td>{t("risk.maxDrawdown")}</td>
                                <td
                                  className={`mono ${risk!.metrics.max_drawdown < -0.1 ? "down" : risk!.metrics.max_drawdown < 0 ? "warn" : ""}`}
                                >
                                  {(risk!.metrics.max_drawdown * 100).toFixed(2)}%
                                </td>
                                <td className="muted">
                                  {Math.abs(risk!.metrics.max_drawdown) > 0.15
                                    ? t("rating.highRisk")
                                    : Math.abs(risk!.metrics.max_drawdown) > 0.08
                                      ? t("rating.watch")
                                      : t("rating.ok")}
                                </td>
                              </tr>
                              <tr>
                                <td>{t("risk.sharpe")}</td>
                                <td className="mono">{risk!.metrics.sharpe_ratio.toFixed(2)}</td>
                                <td className="muted">{ratioGrade(risk!.metrics.sharpe_ratio, 2, 1)}</td>
                              </tr>
                              <tr>
                                <td>{t("risk.sortino")}</td>
                                <td className="mono">{risk!.metrics.sortino_ratio.toFixed(2)}</td>
                                <td className="muted">{ratioGrade(risk!.metrics.sortino_ratio, 2, 1)}</td>
                              </tr>
                              <tr>
                                <td>{t("risk.volatility")}</td>
                                <td className="mono">{(risk!.metrics.volatility * 100).toFixed(2)}%</td>
                                <td className="muted">
                                  {risk!.metrics.volatility > 0.3
                                    ? t("rating.high")
                                    : risk!.metrics.volatility > 0.2
                                      ? t("rating.medium")
                                      : t("rating.low")}
                                </td>
                              </tr>
                              <tr>
                                <td>{t("risk.concentration")}</td>
                                <td className="mono">{(risk!.metrics.concentration_ratio * 100).toFixed(1)}%</td>
                                <td className="muted">
                                  {risk!.metrics.concentration_sector || "-"}
                                  {risk!.metrics.concentration_ratio > 0.4
                                    ? ` · ${t("rating.elevated")}`
                                    : ` · ${t("rating.diversified")}`}
                                </td>
                              </tr>
                              <tr>
                                <td>{t("risk.maxLoss1d")}</td>
                                <td className="mono down">
                                  ¥
                                  {risk!.metrics.max_loss_1d.toLocaleString(numLocale, {
                                    minimumFractionDigits: 2,
                                  })}
                                </td>
                                <td className="muted">{(risk!.metrics.max_loss_1d_pct * 100).toFixed(2)}% (3σ)</td>
                              </tr>
                            </tbody>
                          </table>
                          {risk!.metrics.individual_drawdowns.length > 0 && (
                            <>
                              <h4 className="risk-subheading">{t("risk.stockDrawdown")}</h4>
                              <table className="metrics-table">
                                <thead>
                                  <tr>
                                    <th>{t("risk.stock")}</th>
                                    <th>{t("portfolio.costCol")}</th>
                                    <th>{t("risk.current")}</th>
                                    <th>{t("risk.drawdown")}</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {risk!.metrics.individual_drawdowns.map((d, i) => (
                                    <tr key={i}>
                                      <td>{d.name}</td>
                                      <td className="mono">{d.cost_price?.toFixed(2)}</td>
                                      <td className="mono">{d.current_price?.toFixed(2)}</td>
                                      <td
                                        className={`mono ${(d.drawdown_pct ?? 0) < -0.08 ? "down" : (d.drawdown_pct ?? 0) < 0 ? "warn" : ""}`}
                                      >
                                        {((d.drawdown_pct ?? 0) * 100).toFixed(2)}%
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </>
                          )}
                        </CollapsibleSection>
                      )}
                    </div>
                  )}
                </section>
              )}
            </>
          )}

          {showProcess && (
            <details
              className="risk-agent-fold process-trail-fold"
              open={loading || agentFoldOpen}
              onToggle={(e) => {
                if (!loading) setAgentFoldOpen((e.target as HTMLDetailsElement).open);
              }}
            >
              <summary className="process-trail-summary risk-agent-fold-summary">
                {loading ? t("risk.agentSectionLive") : t("risk.agentSection")}
              </summary>
              <div className="process-trail-body risk-agent-fold-body">
                <StreamFeed
                  streamStatus={riskStream.streamStatus}
                  streamLog={riskStream.streamLog}
                  agentSteps={riskStream.agentSteps}
                  debateRounds={riskStream.debateRounds}
                  judgeVerdict={riskStream.judgeVerdict}
                  voteTally={riskStream.voteTally}
                  activeStreamIds={riskStream.activeStreamIds}
                  masterCommentary={riskStream.masterCommentary}
                  live={loading}
                  riskCompact
                />
              </div>
            </details>
          )}

          {risk && (
            <>
              {risk.portfolio_summary && (
                <p className="risk-portfolio-summary">{risk.portfolio_summary}</p>
              )}

              <section className="risk-alerts-section">
                <h3 className="risk-section-title">
                  <IconAlert size={16} />
                  {t("risk.alertsTitle")}
                  <span className="muted risk-alert-count">{alertCount}</span>
                </h3>
                {risk.alerts.length === 0 ? (
                  <p className="muted risk-no-alerts">{t("risk.noAlerts")}</p>
                ) : (
                  <div className="risk-alert-list">
                    {risk.alerts.map((a, i) => {
                      const tags = alertHoldingTags(a.human_message);
                      return (
                        <CollapsibleSection
                          key={`${a.rule_id}-${i}`}
                          className={`risk-alert-item alert-${a.severity}`}
                          title={localizeRiskRuleId(a.rule_id, t)}
                          summary={
                            <>
                              <span className={`stat-pill severity-${a.severity}`}>
                                {localizeSeverity(a.severity, t)}
                              </span>
                              <span className="risk-alert-oneline">{alertOneLine(a.human_message)}</span>
                            </>
                          }
                          defaultCollapsed
                        >
                          <p className="risk-alert-detail">{a.human_message}</p>
                          {tags.length > 0 && (
                            <div className="alert-holding-tags">
                              {tags.map((h) => (
                                <span className="alert-holding-tag" key={h.symbol}>
                                  {h.name}
                                </span>
                              ))}
                            </div>
                          )}
                        </CollapsibleSection>
                      );
                    })}
                  </div>
                )}
              </section>

              {(risk.llm_analysis || riskStream.judgeVerdict) && (
                <section className="risk-ai-section">
                  <h3 className="risk-section-title">
                    <IconBolt size={16} />
                    {t("risk.aiSummary")}
                  </h3>
                  <div className="card risk-ai-card">
                    {riskStream.judgeVerdict?.summary && (
                      <div className="risk-ai-block">
                        <MarkdownContent text={riskStream.judgeVerdict.summary} />
                      </div>
                    )}
                    {risk.llm_analysis && (
                      <>
                        {risk.llm_analysis.market_assessment && (
                          <div className="risk-ai-block">
                            <strong>{t("risk.market")}</strong>
                            <p>{risk.llm_analysis.market_assessment}</p>
                          </div>
                        )}
                        {risk.llm_analysis.correlation_analysis && (
                          <div className="risk-ai-block">
                            <strong>{t("risk.correlation")}</strong>
                            <p>{risk.llm_analysis.correlation_analysis}</p>
                          </div>
                        )}
                        {risk.llm_analysis.risk_narrative && !riskStream.judgeVerdict?.summary && (
                          <div className="risk-ai-block">
                            <strong>{t("risk.narrative")}</strong>
                            <p>{risk.llm_analysis.risk_narrative}</p>
                          </div>
                        )}
                        {risk.llm_analysis.scenario_analysis.length > 0 && (
                          <div className="risk-ai-block">
                            <strong>{t("risk.scenarios")}</strong>
                            <ul>
                              {risk.llm_analysis.scenario_analysis.map((s, i) => (
                                <li key={i}>{s}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </section>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
