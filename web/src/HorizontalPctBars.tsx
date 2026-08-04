import { formatSignedPct, signedClass } from "./holdingDisplay";

export interface PctBarItem {
  id: string;
  label: string;
  value: number;
  meta?: string;
  onClick?: () => void;
}

interface HorizontalPctBarsProps {
  items: PctBarItem[];
  maxAbs?: number;
  dense?: boolean;
  ariaLabel?: string;
}

function barWidth(value: number, maxAbs: number): number {
  if (maxAbs <= 0) return 0;
  return Math.min(100, (Math.abs(value) / maxAbs) * 100);
}

export function HorizontalPctBars({
  items,
  maxAbs,
  dense = false,
  ariaLabel,
}: HorizontalPctBarsProps) {
  if (items.length === 0) return null;

  const computedMax = maxAbs ?? Math.max(...items.map((item) => Math.abs(item.value)), 0.01);

  return (
    <div
      className={`pct-bar-chart${dense ? " pct-bar-chart-dense" : ""}`}
      role="img"
      aria-label={ariaLabel}
    >
      {items.map((item) => {
        const width = barWidth(item.value, computedMax);
        const positive = item.value >= 0;
        const LabelTag = item.onClick ? "button" : "span";
        return (
          <div key={item.id} className="pct-bar-row">
            <LabelTag
              type={item.onClick ? "button" : undefined}
              className={`pct-bar-label${item.onClick ? " pct-bar-label-btn" : ""}`}
              onClick={item.onClick}
              title={item.label}
            >
              {item.label}
            </LabelTag>
            <div className="pct-bar-track" aria-hidden="true">
              <div className="pct-bar-mid" />
              {positive ? (
                <div
                  className="pct-bar-fill pct-bar-up pct-bar-pos"
                  style={{ width: `${width / 2}%` }}
                />
              ) : (
                <div
                  className="pct-bar-fill pct-bar-down pct-bar-neg"
                  style={{ width: `${width / 2}%` }}
                />
              )}
            </div>
            <span className={`pct-bar-value mono ${signedClass(item.value)}`}>
              {formatSignedPct(item.value)}
            </span>
            {item.meta ? <span className="pct-bar-meta muted">{item.meta}</span> : null}
          </div>
        );
      })}
    </div>
  );
}
