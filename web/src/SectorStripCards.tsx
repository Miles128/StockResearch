import type { CSSProperties } from "react";
import { formatSignedPct, signedClass } from "./holdingDisplay";

export interface SectorStripItem {
  id: string;
  label: string;
  value: number;
  meta?: string;
  onClick?: () => void;
}

interface SectorStripCardsProps {
  items: SectorStripItem[];
  ariaLabel?: string;
}

/** Vertical strip cards for sector boards — sorted worst decline → best. */
export function SectorStripCards({ items, ariaLabel }: SectorStripCardsProps) {
  if (items.length === 0) return null;

  const maxAbs = Math.max(...items.map((item) => Math.abs(item.value)), 0.01);

  return (
    <div className="sector-strip-scroll" role="list" aria-label={ariaLabel}>
      {items.map((item) => {
        const up = item.value >= 0;
        const intensity = Math.min(1, Math.abs(item.value) / maxAbs);
        const fillAlpha = 0.1 + intensity * 0.35;
        const style = {
          "--sector-fill": up
            ? `rgba(220, 38, 38, ${fillAlpha.toFixed(3)})`
            : `rgba(5, 150, 105, ${fillAlpha.toFixed(3)})`,
          "--sector-bar": `${Math.max(8, intensity * 100)}%`,
        } as CSSProperties;

        return (
          <button
            key={item.id}
            type="button"
            role="listitem"
            className={`sector-strip-card ${up ? "sector-strip-up" : "sector-strip-down"}`}
            style={style}
            onClick={item.onClick}
            title={item.meta ? `${item.label} · ${item.meta}` : item.label}
          >
            <span className="sector-strip-bar" aria-hidden="true" />
            <span className="sector-strip-name">{item.label}</span>
            <span
              className={`sector-strip-pct mono ${signedClass(item.value)}`}
            >
              {formatSignedPct(item.value)}
            </span>
            {item.meta ? (
              <span className="sector-strip-meta muted">{item.meta}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
