import { useCallback, useState } from "react";
import { api, type HypothesisVerify } from "./api";
import { EVENT_KEYS, recordEvent } from "./usageTracking";
import { useI18n } from "./i18n";

interface HypothesisVerifyButtonProps {
  symbol: string;
  name?: string;
  /** 默认选中的规则（可选）。 */
  defaultRule?: string;
}

/** 研报卡"验证这条"入口：选预设规则 → 前向收益统计 → 内联展示。 */
export function HypothesisVerifyButton({ symbol, name, defaultRule }: HypothesisVerifyButtonProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [presets, setPresets] = useState<Record<string, string> | null>(null);
  const [rule, setRule] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<HypothesisVerify | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openPanel = useCallback(async () => {
    setOpen((v) => {
      if (v) return false;
      void (async () => {
        setError(null);
        try {
          const presets = await api.hypothesisPresets();
          setPresets(presets);
          const keys = Object.keys(presets);
          setRule(defaultRule && keys.includes(defaultRule) ? defaultRule : (keys[0] ?? ""));
        } catch {
          setError(t("card.verifyPresetsFailed"));
        }
      })();
      return true;
    });
  }, [defaultRule, t]);

  const runVerify = useCallback(async () => {
    if (!rule) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.hypothesisVerify(symbol, rule);
      setResult(res);
      recordEvent(EVENT_KEYS.verifyRun);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("card.verifyFailed"));
    } finally {
      setLoading(false);
    }
  }, [rule, symbol, t]);

  return (
    <span className="hypothesis-verify">
      <button
        type="button"
        className="example-chip"
        onClick={() => void openPanel()}
        title={t("card.verifyTip")}
      >
        {t("card.verifyTitle")}
      </button>
      {open && (
        <div className="hypothesis-verify-panel">
          {presets && (
            <div className="hypothesis-verify-row">
              <select
                className="hypothesis-verify-select"
                value={rule}
                onChange={(e) => setRule(e.target.value)}
              >
                {Object.entries(presets).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="icon-btn"
                disabled={loading || !rule}
                onClick={() => void runVerify()}
              >
                {loading ? "…" : t("card.verifyRun")}
              </button>
            </div>
          )}
          {error && <p className="error hypothesis-verify-error">{error}</p>}
          {result && (
            <div className="hypothesis-verify-result">
              <p className="hypothesis-verify-head">
                <strong>{result.rule_label}</strong>
                {result.point_in_time && (
                  <span className="hypothesis-verify-pit">{t("card.verifyPit")}</span>
                )}
              </p>
              {result.partial && <p className="muted">{t("card.verifyPartial")}</p>}
              {result.windows.length === 0 && (
                <p className="muted">{t("card.verifyNoHits", { name: name ?? symbol })}</p>
              )}
              {result.windows.map((w) => (
                <div key={w.days} className="hypothesis-window">
                  <span className="hypothesis-window-days">{w.days}d</span>
                  <span className="hypothesis-window-hit">
                    {w.hit_rate_pct != null
                      ? `${t("card.verifyHitRate")} ${w.hit_rate_pct.toFixed(0)}%`
                      : "—"}
                  </span>
                  <span className="hypothesis-window-avg">
                    {w.avg_return_pct != null
                      ? `${t("card.verifyAvgReturn")} ${w.avg_return_pct > 0 ? "+" : ""}${w.avg_return_pct.toFixed(2)}%`
                      : "—"}
                  </span>
                  <span className="hypothesis-window-n">n={w.sample_count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </span>
  );
}
