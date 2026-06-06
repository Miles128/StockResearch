import type { HoldingEnriched, RiskCheckup } from "./api";
import { useI18n } from "./i18n";
import { localizeRiskRuleId, localizeSeverity } from "./uiLabels";

interface RiskPanelProps {
  holdings: HoldingEnriched[];
  risk: RiskCheckup | null;
  loading: boolean;
  numLocale: string;
  ratioGrade: (v: number, excellent: number, good: number) => string;
  alertHoldingTags: (message: string) => HoldingEnriched[];
  onRunRisk: () => void;
  onGoPortfolio: () => void;
}

export function RiskPanel({
  holdings,
  risk,
  loading,
  numLocale,
  ratioGrade,
  alertHoldingTags,
  onRunRisk,
  onGoPortfolio,
}: RiskPanelProps) {
  const { t } = useI18n();

  return (
    <div className="panel">
      {holdings.length === 0 ? (
        <div className="risk-empty-cta">
          <p className="muted">{t("risk.emptyHoldings")}</p>
          <button type="button" className="btn btn-primary" onClick={onGoPortfolio}>
            {t("risk.goPortfolio")}
          </button>
        </div>
      ) : (
        <div className="risk-run-panel">
          <p className="muted" style={{ margin: 0 }}>
            {t("risk.hasHoldingsHint").replace("{n}", String(holdings.length))}
          </p>
          <button className="btn btn-primary" onClick={onRunRisk} disabled={loading}>
            {loading ? t("risk.running") : t("risk.run")}
          </button>
        </div>
      )}
      {risk && (
        <>
          <p style={{ margin: "8px 0" }}>{risk.portfolio_summary}</p>

          {risk.metrics && (
            <div className="card">
              <h4>{t("risk.metrics")}</h4>
              <table className="metrics-table">
                <tbody>
                  <tr>
                    <td>{t("risk.sharpe")}</td>
                    <td className="mono">{risk.metrics.sharpe_ratio.toFixed(2)}</td>
                    <td className="muted">{ratioGrade(risk.metrics.sharpe_ratio, 2, 1)}</td>
                  </tr>
                  <tr>
                    <td>{t("risk.sortino")}</td>
                    <td className="mono">{risk.metrics.sortino_ratio.toFixed(2)}</td>
                    <td className="muted">{ratioGrade(risk.metrics.sortino_ratio, 2, 1)}</td>
                  </tr>
                  <tr>
                    <td>{t("risk.calmar")}</td>
                    <td className="mono">{risk.metrics.calmar_ratio.toFixed(2)}</td>
                    <td className="muted">{ratioGrade(risk.metrics.calmar_ratio, 3, 1)}</td>
                  </tr>
                  <tr>
                    <td>{t("risk.infoRatio")}</td>
                    <td className="mono">{risk.metrics.information_ratio.toFixed(2)}</td>
                    <td className="muted">{ratioGrade(risk.metrics.information_ratio, 1, 0.5)}</td>
                  </tr>
                  <tr>
                    <td>{t("risk.maxDrawdown")}</td>
                    <td
                      className={`mono ${risk.metrics.max_drawdown < -0.1 ? "down" : risk.metrics.max_drawdown < 0 ? "warn" : ""}`}
                    >
                      {(risk.metrics.max_drawdown * 100).toFixed(2)}%
                    </td>
                    <td className="muted">
                      {Math.abs(risk.metrics.max_drawdown) > 0.15
                        ? t("rating.highRisk")
                        : Math.abs(risk.metrics.max_drawdown) > 0.08
                          ? t("rating.watch")
                          : t("rating.ok")}
                    </td>
                  </tr>
                  <tr>
                    <td>{t("risk.volatility")}</td>
                    <td className="mono">{(risk.metrics.volatility * 100).toFixed(2)}%</td>
                    <td className="muted">
                      {risk.metrics.volatility > 0.3
                        ? t("rating.high")
                        : risk.metrics.volatility > 0.2
                          ? t("rating.medium")
                          : t("rating.low")}
                    </td>
                  </tr>
                  <tr>
                    <td>{t("risk.concentration")}</td>
                    <td className="mono">{(risk.metrics.concentration_ratio * 100).toFixed(1)}%</td>
                    <td className="muted">
                      {risk.metrics.concentration_sector || "-"} {risk.metrics.concentration_ratio > 0.4 ? t("rating.elevated") : t("rating.diversified")}
                    </td>
                  </tr>
                  <tr>
                    <td>{t("risk.maxLoss1d")}</td>
                    <td className="mono down">
                      ¥{risk.metrics.max_loss_1d.toLocaleString(numLocale, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="muted">{(risk.metrics.max_loss_1d_pct * 100).toFixed(2)}% (3σ)</td>
                  </tr>
                  <tr>
                    <td>{t("risk.expectedLoss")}</td>
                    <td className="mono down">
                      ¥{risk.metrics.expected_loss.toLocaleString(numLocale, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="muted">{(risk.metrics.expected_loss_pct * 100).toFixed(2)}% (PD×LGD×EAD)</td>
                  </tr>
                </tbody>
              </table>
              {risk.metrics.individual_drawdowns.length > 0 && (
                <>
                  <h4 style={{ marginTop: 10 }}>{t("risk.stockDrawdown")}</h4>
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
                      {risk.metrics.individual_drawdowns.map((d, i) => (
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
            </div>
          )}

          {risk.var_result && (
            <div className="card">
              <h4>{t("risk.var")}</h4>
              <div className="stat-row">
                <span className="stat-pill">
                  {t("risk.confidence")} {(risk.var_result.confidence_level * 100).toFixed(0)}%
                </span>
                <span className="stat-pill">
                  {t("risk.horizon")} {risk.var_result.time_horizon_days}
                  {t("risk.days")}
                </span>
                <span className="stat-pill">
                  {t("risk.method")} {risk.var_result.method}
                </span>
              </div>
              <div className="var-display">
                <div className="var-main">
                  <span className="var-label">{t("risk.varAbs")}</span>
                  <span className="var-value down">
                    ¥{risk.var_result.var_value.toLocaleString(numLocale, { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="var-main">
                  <span className="var-label">{t("risk.varPct")}</span>
                  <span className="var-value">{(risk.var_result.var_pct * 100).toFixed(2)}%</span>
                </div>
                <div className="var-main">
                  <span className="var-label">{t("risk.cvar")}</span>
                  <span className="var-value down">
                    ¥{risk.var_result.cvar_value.toLocaleString(numLocale, { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="var-main">
                  <span className="var-label">{t("risk.cvarPct")}</span>
                  <span className="var-value">{(risk.var_result.cvar_pct * 100).toFixed(2)}%</span>
                </div>
              </div>
              <div className="var-bar-container">
                <div className="var-bar-track">
                  <div
                    className="var-bar-fill"
                    style={{ width: `${Math.min(risk.var_result.var_pct * 100 * 2, 100)}%` }}
                  />
                </div>
                <div className="var-bar-labels">
                  <span>0%</span>
                  <span>{(risk.var_result.var_pct * 100).toFixed(1)}%</span>
                  <span>50%</span>
                </div>
              </div>
              {risk.var_result.holdings_var.length > 0 && (
                <table className="metrics-table" style={{ marginTop: 8 }}>
                  <thead>
                    <tr>
                      <th>{t("risk.stock")}</th>
                      <th>{t("risk.weight")}</th>
                      <th>VaR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {risk.var_result.holdings_var.map((h, i) => (
                      <tr key={i}>
                        <td>{h.name}</td>
                        <td className="mono">{((h.weight ?? 0) * 100).toFixed(1)}%</td>
                        <td className="mono down">¥{(h.var_value ?? 0).toLocaleString(numLocale, { minimumFractionDigits: 2 })}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {risk.alerts.map((a, i) => {
            const tags = alertHoldingTags(a.human_message);
            return (
              <div className={`card alert-${a.severity}`} key={i}>
                <h4>{localizeRiskRuleId(a.rule_id, t)}</h4>
                <span className="stat-pill muted">{localizeSeverity(a.severity, t)}</span>
                <p>{a.human_message}</p>
                {tags.length > 0 && (
                  <div className="alert-holding-tags">
                    {tags.map((h) => (
                      <span className="alert-holding-tag" key={h.symbol}>
                        {h.name}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          {risk.llm_analysis && (
            <div className="card">
              <h4>{t("risk.aiAnalysis")}</h4>
              <p>
                <strong>{t("risk.market")}:</strong> {risk.llm_analysis.market_assessment}
              </p>
              <p>
                <strong>{t("risk.correlation")}:</strong> {risk.llm_analysis.correlation_analysis}
              </p>
              <p>
                <strong>{t("risk.narrative")}:</strong> {risk.llm_analysis.risk_narrative}
              </p>
              {risk.llm_analysis.scenario_analysis.length > 0 && (
                <>
                  <span className="field-label">{t("risk.scenarios")}</span>
                  <ul>
                    {risk.llm_analysis.scenario_analysis.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
