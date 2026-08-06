import { useMemo, useState } from "react";
import { useI18n } from "../i18n";
import { loadUsageStats } from "../llmUsageStats";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

/** 设置页 LLM 用量统计块（BYOK 用户可见 token 消耗）。 */
export function UsageStatsBlock() {
  const { t } = useI18n();
  const [version, setVersion] = useState(0);
  const stats = useMemo(() => loadUsageStats(), [version]);

  if (stats.calls === 0) {
    return (
      <section className="settings-section">
        <h4 className="settings-section-title">{t("settings.usageTitle")}</h4>
        <p className="settings-hint">{t("settings.usageEmpty")}</p>
      </section>
    );
  }

  return (
    <section className="settings-section">
      <h4 className="settings-section-title">{t("settings.usageTitle")}</h4>
      <div className="usage-stats-grid">
        <div className="usage-stat">
          <span className="usage-stat-value">{formatTokens(stats.total_tokens)}</span>
          <span className="usage-stat-label">{t("settings.usageTotal")}</span>
        </div>
        <div className="usage-stat">
          <span className="usage-stat-value">{formatTokens(stats.today_tokens)}</span>
          <span className="usage-stat-label">{t("settings.usageToday")}</span>
        </div>
        <div className="usage-stat">
          <span className="usage-stat-value">{stats.calls}</span>
          <span className="usage-stat-label">{t("settings.usageCalls")}</span>
        </div>
        {stats.cost_cny > 0 && (
          <div className="usage-stat">
            <span className="usage-stat-value">¥{stats.cost_cny.toFixed(2)}</span>
            <span className="usage-stat-label">{t("settings.usageCost")}</span>
          </div>
        )}
      </div>
      <button
        type="button"
        className="settings-ghost-btn"
        onClick={() => {
          localStorage.removeItem("stockresearch.llm.usage");
          setVersion((v) => v + 1);
        }}
      >
        {t("settings.usageReset")}
      </button>
    </section>
  );
}
