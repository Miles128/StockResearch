import { useEffect, useState } from "react";
import { api, type SectorMovers } from "./api";
import { formatSignedPct, signedClass } from "./holdingDisplay";
import { useI18n } from "./i18n";
import { CollapsibleSection } from "./CollapsibleSection";

interface SectorMoversPanelProps {
  selectedSector?: string | null;
  onSelectLeader: (symbol: string, name: string) => void;
  onAskSector: (sectorName: string) => void;
}

export function SectorMoversPanel({
  selectedSector,
  onSelectLeader,
  onAskSector,
}: SectorMoversPanelProps) {
  const { t } = useI18n();
  const [data, setData] = useState<SectorMovers | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .sectorMovers()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return null;

  const hasContent = data && (data.gainers.some((g) => g.name) || data.losers.some((l) => l.name));
  if (!hasContent) return null;

  function renderColumn(title: string, items: SectorMovers["gainers"]) {
    return (
      <div className="sector-movers-col">
        <div className="flat-section-title">{title}</div>
        <ul className="sector-movers-list">
          {items.map((item) => (
            <li key={item.code} className="sector-movers-row">
              <button
                type="button"
                className={`sector-movers-name${selectedSector === item.name ? " active" : ""}`}
                onClick={() => onAskSector(item.name)}
              >
                {item.name}
              </button>
              <span className={`mono ${signedClass(item.change_pct)}`}>
                {formatSignedPct(item.change_pct)}
              </span>
              {item.leader_symbol ? (
                <button
                  type="button"
                  className="sector-movers-leader"
                  onClick={() => onSelectLeader(item.leader_symbol, item.leader_name)}
                >
                  {item.leader_name}
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <CollapsibleSection title={t("sectors.title")} className="sector-movers-panel" defaultCollapsed>
      <div className="sector-movers-grid">
        {renderColumn(t("sectors.gainers"), data!.gainers)}
        {renderColumn(t("sectors.losers"), data!.losers)}
      </div>
    </CollapsibleSection>
  );
}
