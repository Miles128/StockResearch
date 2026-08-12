import { useCallback, useEffect, useState } from "react";
import { api, type PortfolioOptimizeMethod, type PortfolioOptimizeResult } from "./api";
import { CollapsibleSection } from "./CollapsibleSection";
import { formatSignedPct, signedClass } from "./holdingDisplay";
import { useI18n } from "./i18n";

const METHODS: PortfolioOptimizeMethod[] = ["min_vol", "risk_parity", "balanced"];

/**
 * V10.29 简单组合优化：最小波动 / 风险平价 / 均衡三预设。
 * 教育参考，不构成投资建议；仅 long-only、单票 ≤40%。
 */
export function PortfolioOptimizeBlock({
  trigger,
}: {
  /** 持仓/自选数量变化时重新拉取（展开后按当前方法请求）。 */
  trigger: string;
}) {
  const { t } = useI18n();
  const [method, setMethod] = useState<PortfolioOptimizeMethod>("min_vol");
  const [result, setResult] = useState<PortfolioOptimizeResult | null>(null);
  const [failed, setFailed] = useState(false);
  const retrigger = `${trigger}:${method}`;

  useEffect(() => {
    let alive = true;
    // 派生状态重置：方法或持仓/自选变化时清掉上一次结果，属预期级联
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFailed(false);
    api
      .portfolioOptimize(method)
      .then((res) => {
        if (alive) setResult(res);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [retrigger]);

  const selectMethod = useCallback((m: PortfolioOptimizeMethod) => {
    setMethod(m);
    setResult(null);
    setFailed(false);
  }, []);

  const loading = !failed && result === null;

  const label = (m: PortfolioOptimizeMethod) =>
    t(
      `portfolio.optimizeMethod${m === "min_vol" ? "MinVol" : m === "risk_parity" ? "RiskParity" : "Balanced"}`,
    );

  return (
    <CollapsibleSection
      title={t("portfolio.optimizeTitle")}
      summary={label(method)}
      defaultCollapsed
      headerExtra={
        <div className="optimize-method-switch" onClick={(e) => e.stopPropagation()}>
          {METHODS.map((m) => (
            <button
              key={m}
              type="button"
              className={`optimize-method-btn${method === m ? " active" : ""}`}
              onClick={() => selectMethod(m)}
            >
              {label(m)}
            </button>
          ))}
        </div>
      }
    >
      {loading && <p className="muted flat-empty">{t("portfolio.loading")}</p>}
      {!loading && failed && <p className="muted flat-empty">{t("portfolio.optimizeError")}</p>}
      {!loading && !failed && result && (
        <div className="optimize-body">
          {result.rows.length === 0 ? (
            <p className="muted flat-empty">{result.explanation}</p>
          ) : (
            <>
              <table className="metrics-table optimize-table">
                <thead>
                  <tr>
                    <th>{t("portfolio.optimizeSymbol")}</th>
                    <th>{t("portfolio.optimizeCurrent")}</th>
                    <th>{t("portfolio.optimizeProposed")}</th>
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((r) => (
                    <tr key={r.symbol}>
                      <td title={r.name}>
                        {r.symbol} {r.name}
                      </td>
                      <td className="mono">{(r.current_weight * 100).toFixed(1)}%</td>
                      <td className={`mono ${signedClass(r.optimal_weight - r.current_weight)}`}>
                        {(r.optimal_weight * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                  {result.cash_weight > 0 && (
                    <tr>
                      <td className="muted">{t("portfolio.optimizeCash")}</td>
                      <td className="mono muted">—</td>
                      <td className="mono">{(result.cash_weight * 100).toFixed(0)}%</td>
                    </tr>
                  )}
                </tbody>
              </table>
              <p className="optimize-metrics mono">
                <span>
                  {t("portfolio.optimizeVol")}:{" "}
                  {result.current_vol != null ? `${result.current_vol.toFixed(1)}%` : "—"} →{" "}
                  {result.optimal_vol != null ? `${result.optimal_vol.toFixed(1)}%` : "—"}
                </span>
                {result.optimal_return != null && (
                  <span>
                    {t("portfolio.optimizeRet")}:{" "}
                    <b className={signedClass(result.optimal_return)}>
                      {formatSignedPct(result.optimal_return)}
                    </b>
                  </span>
                )}
              </p>
              <p className="muted optimize-explanation">{result.explanation}</p>
              <p className="muted optimize-disclaimer">{result.disclaimer}</p>
            </>
          )}
        </div>
      )}
    </CollapsibleSection>
  );
}
