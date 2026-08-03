import { useState, type ReactNode } from "react";
import type { HoldingEnriched, RiskCheckup } from "./api";
import { CollapsibleSection } from "./CollapsibleSection";
import { useI18n } from "./i18n";

const PALETTE = [
  "#6366f1",
  "#f59e0b",
  "#ef4444",
  "#22c55e",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
  "#64748b",
];

const TOP_VISIBLE = 5;

export interface ChartSlice {
  key: string;
  label: string;
  value: number;
  color: string;
}

function colorAt(i: number): string {
  return PALETTE[i % PALETTE.length];
}

function toSlices(
  items: { key: string; label: string; value: number }[],
  minShare = 0.02,
  otherLabel = "其他",
): ChartSlice[] {
  const positive = items.filter((x) => x.value > 0);
  const total = positive.reduce((s, x) => s + x.value, 0);
  if (total <= 0) return [];
  const slices = positive.map((x, i) => ({
    ...x,
    color: colorAt(i),
  }));
  const main = slices.filter((s) => s.value / total >= minShare);
  const rest = slices.filter((s) => s.value / total < minShare);
  if (rest.length === 0) return main;
  const otherValue = rest.reduce((s, x) => s + x.value, 0);
  return [
    ...main,
    {
      key: "__other__",
      label: otherLabel,
      value: otherValue,
      color: "#94a3b8",
    },
  ];
}

function piePaths(
  slices: ChartSlice[],
  cx: number,
  cy: number,
  r: number,
): ReactNode[] {
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;
  let acc = 0;
  return slices.map((slice) => {
    const start = (acc / total) * Math.PI * 2 - Math.PI / 2;
    acc += slice.value;
    const end = (acc / total) * Math.PI * 2 - Math.PI / 2;
    if (slice.value <= 0) return null;
    const large = end - start > Math.PI ? 1 : 0;
    const x1 = cx + r * Math.cos(start);
    const y1 = cy + r * Math.sin(start);
    const x2 = cx + r * Math.cos(end);
    const y2 = cy + r * Math.sin(end);
    return (
      <path
        key={slice.key}
        d={`M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`}
        fill={slice.color}
        stroke="var(--bbg-black, #0a0a0a)"
        strokeWidth="1"
      />
    );
  });
}

function RiskPieCard({
  title,
  subtitle,
  slices,
  centerLabel,
}: {
  title: string;
  subtitle?: string;
  slices: ChartSlice[];
  centerLabel?: string;
}) {
  const total = slices.reduce((s, x) => s + x.value, 0);
  if (total <= 0) return null;

  return (
    <div className="risk-chart-card">
      <h4 className="risk-chart-title">{title}</h4>
      {subtitle && <p className="risk-chart-subtitle muted">{subtitle}</p>}
      <div className="risk-chart-body">
        <svg className="risk-pie" viewBox="0 0 120 120" aria-hidden="true">
          {piePaths(slices, 60, 60, 52)}
          {centerLabel && (
            <text x="60" y="58" textAnchor="middle" className="risk-pie-center">
              {centerLabel}
            </text>
          )}
        </svg>
        <ul className="risk-chart-legend">
          {slices.map((s) => {
            const pct = (s.value / total) * 100;
            return (
              <li key={s.key}>
                <span
                  className="risk-chart-legend-dot"
                  style={{ background: s.color }}
                />
                <span className="risk-chart-legend-label" title={s.label}>
                  {s.label}
                </span>
                <span className="risk-chart-legend-pct mono">
                  {pct.toFixed(1)}%
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

function ExpandToggle({
  expanded,
  hiddenCount,
  onToggle,
  showAllLabel,
  showLessLabel,
}: {
  expanded: boolean;
  hiddenCount: number;
  onToggle: () => void;
  showAllLabel: string;
  showLessLabel: string;
}) {
  if (hiddenCount <= 0) return null;
  return (
    <button
      type="button"
      className="btn btn-ghost btn-sm risk-chart-expand-btn"
      onClick={onToggle}
    >
      {expanded ? showLessLabel : showAllLabel}
    </button>
  );
}

function MiniBar({
  pct,
  tone,
}: {
  pct: number;
  tone: "weight" | "var" | "drawdown";
}) {
  return (
    <div className="risk-mini-bar">
      <div className="risk-bar-track">
        <div
          className={`risk-bar-fill risk-bar-fill-${tone === "weight" ? "weight" : tone === "var" ? "var" : ""}`}
          style={{
            width: `${Math.min(Math.abs(pct), 100)}%`,
            ...(tone === "drawdown" ? { background: "#ef4444" } : {}),
          }}
        />
      </div>
    </div>
  );
}

function RiskCompareDenseTable({
  rows,
  stockLabel,
  weightLabel,
  varLabel,
  showAllLabel,
  showLessLabel,
}: {
  rows: {
    key: string;
    label: string;
    weightPct: number;
    varSharePct: number;
  }[];
  stockLabel: string;
  weightLabel: string;
  varLabel: string;
  showAllLabel: string;
  showLessLabel: string;
}) {
  const [expanded, setExpanded] = useState(false);
  if (rows.length === 0) return null;

  const hiddenCount = Math.max(0, rows.length - TOP_VISIBLE);
  const visible = expanded ? rows : rows.slice(0, TOP_VISIBLE);
  const scrollable = expanded && rows.length > 8;

  return (
    <div
      className={`risk-dense-table-wrap${scrollable ? " is-scrollable" : ""}`}
    >
      <table className="risk-dense-table">
        <thead>
          <tr>
            <th>{stockLabel}</th>
            <th className="risk-dense-num-col">{weightLabel}</th>
            <th className="risk-dense-num-col">{varLabel}</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((row) => (
            <tr key={row.key}>
              <td className="risk-dense-name" title={row.label}>
                {row.label}
              </td>
              <td className="risk-dense-metric">
                <MiniBar pct={row.weightPct} tone="weight" />
                <span className="mono">{row.weightPct.toFixed(1)}%</span>
              </td>
              <td className="risk-dense-metric">
                <MiniBar pct={row.varSharePct} tone="var" />
                <span className="mono">{row.varSharePct.toFixed(1)}%</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ExpandToggle
        expanded={expanded}
        hiddenCount={hiddenCount}
        onToggle={() => setExpanded((v) => !v)}
        showAllLabel={showAllLabel}
        showLessLabel={showLessLabel}
      />
    </div>
  );
}

function RiskDrawdownDenseTable({
  rows,
  stockLabel,
  drawdownLabel,
  showAllLabel,
  showLessLabel,
}: {
  rows: { key: string; label: string; value: number }[];
  stockLabel: string;
  drawdownLabel: string;
  showAllLabel: string;
  showLessLabel: string;
}) {
  const [expanded, setExpanded] = useState(false);
  if (rows.length === 0) return null;

  const hiddenCount = Math.max(0, rows.length - TOP_VISIBLE);
  const visible = expanded ? rows : rows.slice(0, TOP_VISIBLE);
  const scrollable = expanded && rows.length > 8;

  return (
    <div
      className={`risk-dense-table-wrap${scrollable ? " is-scrollable" : ""}`}
    >
      <table className="risk-dense-table">
        <thead>
          <tr>
            <th>{stockLabel}</th>
            <th className="risk-dense-num-col">{drawdownLabel}</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((row) => (
            <tr key={row.key}>
              <td className="risk-dense-name" title={row.label}>
                {row.label}
              </td>
              <td className="risk-dense-metric">
                <MiniBar pct={row.value * 100} tone="drawdown" />
                <span className="mono down">
                  {(row.value * 100).toFixed(1)}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ExpandToggle
        expanded={expanded}
        hiddenCount={hiddenCount}
        onToggle={() => setExpanded((v) => !v)}
        showAllLabel={showAllLabel}
        showLessLabel={showLessLabel}
      />
    </div>
  );
}

interface RiskSourceChartsProps {
  risk: RiskCheckup;
  holdings: HoldingEnriched[];
  numLocale: string;
}

export function RiskSourceCharts({
  risk,
  holdings,
  numLocale,
}: RiskSourceChartsProps) {
  const { t } = useI18n();

  const holdingsVar = risk.var_result?.holdings_var ?? [];
  const varTotal = holdingsVar.reduce((s, h) => s + (h.var_value ?? 0), 0);

  const varSlices = toSlices(
    holdingsVar.map((h) => ({
      key: h.symbol ?? h.name,
      label: h.name,
      value: h.var_value ?? 0,
    })),
    0.02,
    t("risk.chartOther"),
  );

  const sectorMap = new Map<string, number>();
  for (const hv of holdingsVar) {
    const sym = hv.symbol ?? "";
    const sector =
      holdings.find((h) => h.symbol === sym)?.sector?.trim() ||
      t("risk.chartUnknownSector");
    sectorMap.set(sector, (sectorMap.get(sector) ?? 0) + (hv.var_value ?? 0));
  }
  const sectorVarSlices = toSlices(
    [...sectorMap.entries()].map(([label, value]) => ({
      key: label,
      label,
      value,
    })),
    0.02,
    t("risk.chartOther"),
  );

  const compareRows = holdingsVar
    .map((h) => {
      const varShare = varTotal > 0 ? ((h.var_value ?? 0) / varTotal) * 100 : 0;
      return {
        key: h.symbol ?? h.name,
        label: h.name,
        weightPct: (h.weight ?? 0) * 100,
        varSharePct: varShare,
      };
    })
    .sort((a, b) => b.varSharePct - a.varSharePct);

  const drawdownRows = (risk.metrics?.individual_drawdowns ?? [])
    .filter((d) => d.name && (d.drawdown_pct ?? 0) < 0)
    .map((d) => ({
      key: d.name!,
      label: d.name!,
      value: Math.abs(d.drawdown_pct ?? 0),
    }))
    .sort((a, b) => b.value - a.value);

  const hasPies = varSlices.length > 0 || sectorVarSlices.length > 1;
  const hasCompare = compareRows.length > 0;
  const hasDrawdown = drawdownRows.length > 0;

  if (!hasPies && !hasCompare && !hasDrawdown) return null;

  const showAllLabel = t("risk.chartShowAll", {
    n: String(compareRows.length),
  });
  const showLessLabel = t("risk.chartShowLess");
  const drawdownShowAll = t("risk.chartShowAll", {
    n: String(drawdownRows.length),
  });

  return (
    <section className="risk-source-charts">
      <h3 className="risk-section-title">{t("risk.sourceCharts")}</h3>

      {hasPies && (
        <div className="risk-charts-grid risk-charts-grid-primary">
          <RiskPieCard
            title={t("risk.chartVarShare")}
            subtitle={t("risk.chartVarShareHint")}
            slices={varSlices}
            centerLabel={
              varTotal > 0
                ? `¥${Math.round(varTotal).toLocaleString(numLocale)}`
                : undefined
            }
          />
          {sectorVarSlices.length > 1 && (
            <RiskPieCard
              title={t("risk.chartSectorVar")}
              subtitle={t("risk.chartSectorVarHint")}
              slices={sectorVarSlices}
            />
          )}
        </div>
      )}

      <div className="risk-charts-details">
        {hasCompare && (
          <CollapsibleSection
            title={t("risk.chartWeightVsVar")}
            summary={
              <span className="muted">
                {t("risk.chartRowCount", { n: compareRows.length })}
              </span>
            }
            defaultCollapsed
          >
            <p className="risk-chart-subtitle muted">
              {t("risk.chartWeightVsVarHint")}
            </p>
            <RiskCompareDenseTable
              rows={compareRows}
              stockLabel={t("risk.stock")}
              weightLabel={t("risk.chartWeight")}
              varLabel={t("risk.var")}
              showAllLabel={showAllLabel}
              showLessLabel={showLessLabel}
            />
          </CollapsibleSection>
        )}

        {hasDrawdown && (
          <CollapsibleSection
            title={t("risk.chartDrawdownSource")}
            summary={
              <span className="muted">
                {t("risk.chartRowCount", { n: drawdownRows.length })}
              </span>
            }
            defaultCollapsed
          >
            <p className="risk-chart-subtitle muted">
              {t("risk.chartDrawdownHint")}
            </p>
            <RiskDrawdownDenseTable
              rows={drawdownRows}
              stockLabel={t("risk.stock")}
              drawdownLabel={t("risk.drawdown")}
              showAllLabel={drawdownShowAll}
              showLessLabel={showLessLabel}
            />
          </CollapsibleSection>
        )}
      </div>
    </section>
  );
}
