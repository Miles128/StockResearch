/**
 * 资产配置参考面板（投顾模式专属）
 *
 * 根据用户的风险等级 + 现金流，展示股/债/现金的参考配置。
 * 这是教育参考，不是投资指令（PRD §8 合规）。
 */

import { useEffect, useState } from "react";
import { api, type AssetAllocation } from "./api";
import { useI18n } from "./i18n";
import type { RiskTolerance } from "./modeSettings";

interface AssetAllocationPanelProps {
  riskTolerance: RiskTolerance;
  monthlyIncome?: number;
}

const ALLOCATION_COLORS: Record<string, string> = {
  股票: "#e15554",
  债券: "#3bb4f2",
  现金: "#52c41a",
};

export function AssetAllocationPanel({
  riskTolerance,
  monthlyIncome,
}: AssetAllocationPanelProps) {
  const { t } = useI18n();
  const [allocation, setAllocation] = useState<AssetAllocation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadAllocation() {
    try {
      setLoading(true);
      setError("");
      const result = await api.advisorAllocation(riskTolerance, monthlyIncome);
      setAllocation(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAllocation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [riskTolerance, monthlyIncome]);

  const riskLabelKey = `allocation.${riskTolerance}`;

  return (
    <div className="panel allocation-panel">
      <div className="allocation-header">
        <div>
          <h3 className="allocation-title">{t("allocation.title")}</h3>
          <p className="allocation-subtitle">{t("allocation.subtitle")}</p>
        </div>
        <button
          type="button"
          className="btn btn-secondary allocation-refresh-btn"
          onClick={() => void loadAllocation()}
          disabled={loading}
        >
          {loading ? t("allocation.loading") : t("allocation.refresh")}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {loading && !allocation && (
        <div className="allocation-loading">{t("allocation.loading")}</div>
      )}

      {allocation && (
        <>
          <div className="allocation-risk-badge">
            <span className="allocation-risk-label">{t("allocation.riskLevel")}：</span>
            <span className={`allocation-risk-value risk-${allocation.risk_tolerance}`}>
              {t(riskLabelKey)}
            </span>
          </div>

          {/* 配置比例可视化 */}
          <div className="allocation-bars">
            {Object.entries(allocation.allocation).map(([key, value]) => (
              <div key={key} className="allocation-bar-item">
                <div className="allocation-bar-label">
                  <span className="allocation-bar-name">{key}</span>
                  <span className="allocation-bar-pct">{Math.round(value * 100)}%</span>
                </div>
                <div className="allocation-bar-track">
                  <div
                    className="allocation-bar-fill"
                    style={{
                      width: `${value * 100}%`,
                      backgroundColor: ALLOCATION_COLORS[key] || "#888",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* 配置说明 */}
          <div className="allocation-section">
            <h4 className="allocation-section-title">{t("allocation.rationale")}</h4>
            <p className="allocation-section-text">{allocation.rationale}</p>
          </div>

          {/* 现金流影响 */}
          {allocation.cash_flow_impact && (
            <div className="allocation-section">
              <h4 className="allocation-section-title">{t("allocation.cashFlowImpact")}</h4>
              <p className="allocation-section-text">{allocation.cash_flow_impact}</p>
            </div>
          )}

          {/* 应急资金建议 */}
          {allocation.emergency_fund_note && (
            <div className="allocation-section">
              <h4 className="allocation-section-title">{t("allocation.emergencyFund")}</h4>
              <p className="allocation-section-text">{allocation.emergency_fund_note}</p>
            </div>
          )}

          {/* 未填写月收入提示 */}
          {!allocation.cash_flow_impact && (
            <div className="allocation-section allocation-no-income">
              <p className="allocation-section-text muted">{t("allocation.noIncome")}</p>
            </div>
          )}

          <p className="allocation-disclaimer">{t("allocation.educationalNote")}</p>
        </>
      )}
    </div>
  );
}
