/** Decorative mini sparkline for index ticker cards (synthetic from day change). */

function sparkPoints(changePct: number, width = 72, height = 28, points = 14): string {
  const trend = Math.max(-1, Math.min(1, changePct / 3));
  const coords: [number, number][] = [];
  for (let i = 0; i < points; i += 1) {
    const x = (i / (points - 1)) * width;
    const wave = Math.sin(i * 0.85) * 0.18 + Math.cos(i * 0.45) * 0.12;
    const progress = i / (points - 1);
    const y = height / 2 - (progress * trend * (height * 0.38) + wave * (height * 0.22));
    coords.push([x, y]);
  }
  return coords
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
}

export function TickerSparkline({ changePct }: { changePct: number }) {
  const up = changePct >= 0;
  return (
    <svg
      className="ticker-sparkline"
      viewBox="0 0 72 28"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d={sparkPoints(changePct)}
        fill="none"
        stroke={up ? "var(--bbg-up)" : "var(--bbg-down)"}
        strokeWidth="2.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.85"
      />
    </svg>
  );
}
