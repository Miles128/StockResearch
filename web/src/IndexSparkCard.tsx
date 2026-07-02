import type { IndexIntraday } from "./api";
import { formatPrice, formatSignedPct, signedClass } from "./holdingDisplay";

interface IndexSparkCardProps {
  name: string;
  symbol: string;
  price: number;
  changePct: number;
  intraday?: IndexIntraday | null;
  onClick?: () => void;
}

function sparkPath(points: { price: number }[], width: number, height: number): string {
  if (points.length < 2) return "";
  const prices = points.map((p) => p.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  return points
    .map((p, i) => {
      const x = i * step;
      const y = height - ((p.price - min) / span) * (height - 4) - 2;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

/** Index tile with faint intraday curve — 红涨绿跌 */
export function IndexSparkCard({
  name,
  symbol,
  price,
  changePct,
  intraday,
  onClick,
}: IndexSparkCardProps) {
  const up = changePct >= 0;
  const sparkClass = up ? "index-spark-up" : "index-spark-down";
  const path = intraday?.points?.length ? sparkPath(intraday.points, 120, 40) : "";

  return (
    <button type="button" className={`index-spark-card ${sparkClass}`} onClick={onClick}>
      {path ? (
        <svg className="index-spark-bg" viewBox="0 0 120 40" preserveAspectRatio="none" aria-hidden="true">
          <path className="index-spark-area" d={`${path} L120,40 L0,40 Z`} />
          <path className="index-spark-line" d={path} fill="none" />
        </svg>
      ) : null}
      <div className="index-spark-body">
        <div className="index-spark-head">
          <span className="index-spark-name">{name}</span>
          <span className="mono muted index-spark-symbol">{symbol}</span>
        </div>
        <div className="index-spark-foot">
          <span className="index-spark-price mono">{formatPrice(price)}</span>
          <span className={`index-spark-pct mono ${signedClass(changePct)}`}>
            {formatSignedPct(changePct)}
          </span>
        </div>
      </div>
    </button>
  );
}
