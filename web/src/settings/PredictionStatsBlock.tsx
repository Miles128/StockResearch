import { useCallback, useEffect, useState } from "react";
import { api, type Prediction, type PredictionStats } from "../api";
import { useI18n } from "../i18n";

function directionLabel(direction: Prediction["direction"], t: (k: string) => string): string {
  if (direction === "bullish") return t("settings.predictionDirBullish");
  if (direction === "bearish") return t("settings.predictionDirBearish");
  return t("settings.predictionDirNeutral");
}

function confidenceLabel(confidence: Prediction["confidence"], t: (k: string) => string): string {
  if (confidence === "high") return t("settings.predictionConfHigh");
  if (confidence === "medium") return t("settings.predictionConfMedium");
  return t("settings.predictionConfLow");
}

function outcomeClass(outcome: Prediction["outcome"]): string {
  if (outcome === "correct") return "prediction-outcome-correct";
  if (outcome === "incorrect") return "prediction-outcome-incorrect";
  return "prediction-outcome-neutral";
}

/** 设置页「预测准确率」块（Phase 12a）：全局命中率 + 校准 + 近期预测记录。 */
export function PredictionStatsBlock() {
  const { t } = useI18n();
  const [stats, setStats] = useState<PredictionStats | null>(null);
  const [list, setList] = useState<Prediction[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [statsRes, listRes] = await Promise.all([
        api.predictionStats(),
        api.predictions({ limit: 10 }),
      ]);
      setStats(statsRes);
      setList(listRes);
    } catch {
      setError(t("settings.predictionLoadFailed"));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const confidenceBuckets = stats ? Object.entries(stats.by_confidence) : [];
  const directionBuckets = stats ? Object.entries(stats.by_direction) : [];

  return (
    <section className="settings-section">
      <h4 className="settings-section-title">{t("settings.predictionTitle")}</h4>
      <p className="settings-hint">{t("settings.predictionHint")}</p>
      {error && <p className="error settings-analysis-note">{error}</p>}
      {stats && stats.scored === 0 && (
        <p className="settings-muted">{t("settings.predictionEmpty")}</p>
      )}
      {stats && stats.scored > 0 && (
        <>
          <div className="usage-stats-grid prediction-stats-grid">
            <div className="usage-stat">
              <span className="usage-stat-value">
                {stats.hit_rate != null ? `${(stats.hit_rate * 100).toFixed(0)}%` : "—"}
              </span>
              <span className="usage-stat-label">{t("settings.predictionHitRate")}</span>
            </div>
            <div className="usage-stat">
              <span className="usage-stat-value">{stats.correct}</span>
              <span className="usage-stat-label">{t("settings.predictionCorrect")}</span>
            </div>
            <div className="usage-stat">
              <span className="usage-stat-value">{stats.incorrect}</span>
              <span className="usage-stat-label">{t("settings.predictionIncorrect")}</span>
            </div>
            <div className="usage-stat">
              <span className="usage-stat-value">{stats.neutral}</span>
              <span className="usage-stat-label">{t("settings.predictionNeutral")}</span>
            </div>
          </div>

          {(confidenceBuckets.length > 0 || directionBuckets.length > 0) && (
            <div className="prediction-calibration">
              {confidenceBuckets.length > 0 && (
                <details className="prediction-calibration-block">
                  <summary>{t("settings.predictionByConfidence")}</summary>
                  {confidenceBuckets.map(([conf, counts]) => {
                    const denom = counts.correct + counts.incorrect;
                    return (
                      <div key={conf} className="prediction-calibration-row">
                        <span className="prediction-calibration-label">
                          {confidenceLabel(conf as Prediction["confidence"], t)}
                        </span>
                        <span className="prediction-calibration-bar">
                          <span
                            className="prediction-calibration-fill"
                            style={{
                              width: `${denom ? (counts.correct / denom) * 100 : 0}%`,
                            }}
                          />
                        </span>
                        <span className="prediction-calibration-value">
                          {denom ? `${Math.round((counts.correct / denom) * 100)}%` : "—"}
                          <span className="muted">
                            {" "}
                            ({counts.correct}/{denom})
                          </span>
                        </span>
                      </div>
                    );
                  })}
                </details>
              )}
              {directionBuckets.length > 0 && (
                <details className="prediction-calibration-block">
                  <summary>{t("settings.predictionByDirection")}</summary>
                  {directionBuckets.map(([dir, counts]) => {
                    const denom = counts.correct + counts.incorrect;
                    return (
                      <div key={dir} className="prediction-calibration-row">
                        <span className="prediction-calibration-label">
                          {directionLabel(dir as Prediction["direction"], t)}
                        </span>
                        <span className="prediction-calibration-bar">
                          <span
                            className="prediction-calibration-fill"
                            style={{
                              width: `${denom ? (counts.correct / denom) * 100 : 0}%`,
                            }}
                          />
                        </span>
                        <span className="prediction-calibration-value">
                          {denom ? `${Math.round((counts.correct / denom) * 100)}%` : "—"}
                          <span className="muted">
                            {" "}
                            ({counts.correct}/{denom})
                          </span>
                        </span>
                      </div>
                    );
                  })}
                </details>
              )}
            </div>
          )}
        </>
      )}
      {list.length > 0 && (
        <ul className="prediction-list">
          {list.map((p) => (
            <li key={p.id} className={`prediction-row ${outcomeClass(p.outcome)}`}>
              <span className="prediction-row-name">
                {p.name} · {p.symbol}
              </span>
              <span className="prediction-row-dir">
                {directionLabel(p.direction, t)} · {confidenceLabel(p.confidence, t)}
              </span>
              <span className="prediction-row-meta">
                {p.status === "scored"
                  ? p.outcome === "correct"
                    ? `✓ ${t("settings.predictionCorrect")}`
                    : p.outcome === "incorrect"
                      ? `✗ ${t("settings.predictionIncorrect")}`
                      : t("settings.predictionNeutral")
                  : `${t("settings.predictionDue")} ${p.due_at}`}
                {p.actual_return_pct != null && (
                  <span className={p.actual_return_pct >= 0 ? "up" : "down"}>
                    {" "}
                    {p.actual_return_pct > 0 ? "+" : ""}
                    {p.actual_return_pct.toFixed(2)}%
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
