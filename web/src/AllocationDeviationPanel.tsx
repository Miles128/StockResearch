/**
 * Expert-mode sector target vs actual weights (display only — no rebalance engine).
 */

import { useEffect, useMemo, useState } from "react";
import { api, type AllocationDeviation, type HoldingEnriched } from "./api";
import { useI18n } from "./i18n";

const STORAGE_KEY = "stockresearch.sector.targets";

function loadTargets(): Record<string, number> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, number>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveTargets(targets: Record<string, number>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(targets));
}

export function AllocationDeviationPanel({ holdings }: { holdings: HoldingEnriched[] }) {
  const { t } = useI18n();
  const sectors = useMemo(() => {
    const set = new Set(holdings.map((h) => h.sector || t("allocation.unknownSector")));
    return Array.from(set).sort();
  }, [holdings, t]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [result, setResult] = useState<AllocationDeviation | "loading" | "error" | null>(null);

  useEffect(() => {
    const saved = loadTargets();
    const next: Record<string, string> = {};
    for (const s of sectors) {
      next[s] = saved[s] != null ? String(Math.round(saved[s] * 100)) : "";
    }
    // sectors 变化时重置草稿：派生状态同步，属预期级联
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDraft(next);
  }, [sectors]);

  async function runCompare() {
    const targets: Record<string, number> = {};
    for (const [sector, text] of Object.entries(draft)) {
      const n = Number(text);
      if (Number.isFinite(n) && n > 0) targets[sector] = n;
    }
    const normalized: Record<string, number> = {};
    const sum = Object.values(targets).reduce((a, b) => a + b, 0);
    if (sum > 0) {
      for (const [k, v] of Object.entries(targets)) {
        normalized[k] = v / 100;
      }
      saveTargets(normalized);
    }
    setResult("loading");
    try {
      setResult(await api.allocationDeviation(targets));
    } catch {
      setResult("error");
    }
  }

  if (holdings.length === 0) {
    return (
      <div className="panel allocation-panel">
        <h3 className="allocation-title">{t("allocation.deviationTitle")}</h3>
        <p className="settings-muted">{t("allocation.deviationEmpty")}</p>
      </div>
    );
  }

  return (
    <div className="panel allocation-panel">
      <div className="allocation-header">
        <div>
          <h3 className="allocation-title">{t("allocation.deviationTitle")}</h3>
          <p className="allocation-subtitle">{t("allocation.deviationHint")}</p>
        </div>
        <button
          type="button"
          className="btn btn-secondary allocation-refresh-btn"
          onClick={() => void runCompare()}
        >
          {result === "loading" ? "…" : t("allocation.deviationCompare")}
        </button>
      </div>
      <div className="allocation-bars">
        {sectors.map((sector) => (
          <label key={sector} className="settings-field">
            <span>
              {sector} {t("allocation.targetPct")}
            </span>
            <input
              type="number"
              min={0}
              max={100}
              value={draft[sector] ?? ""}
              onChange={(e) => setDraft((prev) => ({ ...prev, [sector]: e.target.value }))}
              placeholder="%"
            />
          </label>
        ))}
      </div>
      {result === "error" ? (
        <p className="settings-muted">{t("allocation.deviationFailed")}</p>
      ) : null}
      {result && result !== "loading" && result !== "error" ? (
        <ul className="report-history-list">
          {result.rows.map((row) => (
            <li key={row.sector} className="settings-muted">
              {row.sector}：{t("allocation.actual")} {(row.actual * 100).toFixed(1)}% ·{" "}
              {t("allocation.target")} {(row.target * 100).toFixed(1)}% · Δ{" "}
              {(row.delta * 100).toFixed(1)}pp
            </li>
          ))}
          {(result.notes ?? []).map((n) => (
            <li key={n} className="settings-muted">
              {n}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
