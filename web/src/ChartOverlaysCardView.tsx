import { useState } from "react";
import type { ChartOverlaySet } from "./api";
import { publishChartOverlays } from "./chartOverlayBus";
import { useI18n } from "./i18n";

interface Props {
  data: ChartOverlaySet;
}

export function ChartOverlaysCardView({ data }: Props) {
  const { t } = useI18n();
  const [applied, setApplied] = useState(false);

  return (
    <div className="card chart-overlays-card">
      <div className="light-research-head">
        <h4>
          {t("overlays.title")} · {data.symbol}
        </h4>
        <div className="stat-row">
          <span className="stat-pill">
            {data.overlays.length} {t("overlays.lines")}
          </span>
          {data.overlays.length > 0 && (
            <button
              type="button"
              className="example-chip"
              disabled={applied}
              onClick={() => {
                publishChartOverlays(data);
                setApplied(true);
              }}
            >
              {applied ? t("overlays.applied") : t("overlays.showOnChart")}
            </button>
          )}
        </div>
      </div>
      {data.overlays.length === 0 ? (
        <p className="muted">{t("overlays.none")}</p>
      ) : (
        <ul className="chart-overlays-list">
          {data.overlays.map((overlay) => (
            <li key={overlay.id}>
              <span className={`stat-pill ${overlay.side === "support" ? "up" : "down"}`}>
                {overlay.side === "support" ? t("overlays.support") : t("overlays.resistance")}
              </span>
              <span className="muted">{overlay.rationale}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
