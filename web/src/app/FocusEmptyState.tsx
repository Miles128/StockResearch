import { memo } from "react";
import { ActionCenter } from "../ActionCenter";
import { BackendHealthBanner } from "../BackendHealthBanner";
import { DemoBanner } from "../DemoBanner";
import { SectorMoversPanel } from "../SectorMoversPanel";

interface FocusEmptyStateProps {
  holdingsCount: number;
  isDemo: boolean;
  demoLoading: boolean;
  highlightSector: string | null;
  onLoadDemo: () => void;
  onClearDemo: () => void;
  onGoPortfolio: () => void;
  onSelectLeader: (symbol: string, name: string) => void;
  onAskSector: (name: string) => void;
  onNavigate: (target: string) => void;
  onChatQuery: (query: string) => void;
}

/** Focus-tab landing state (health/demo banners + sector movers + action center). */
export const FocusEmptyState = memo(function FocusEmptyState({
  holdingsCount,
  isDemo,
  demoLoading,
  highlightSector,
  onLoadDemo,
  onClearDemo,
  onGoPortfolio,
  onSelectLeader,
  onAskSector,
  onNavigate,
  onChatQuery,
}: FocusEmptyStateProps) {
  return (
    <>
      <BackendHealthBanner />
      {!isDemo && holdingsCount === 0 && (
        <DemoBanner
          onLoad={onLoadDemo}
          onClear={onClearDemo}
          isDemo={isDemo}
          loading={demoLoading}
        />
      )}
      {isDemo && (
        <DemoBanner
          onLoad={onLoadDemo}
          onClear={onClearDemo}
          onGoPortfolio={onGoPortfolio}
          isDemo={isDemo}
          loading={demoLoading}
        />
      )}
      <SectorMoversPanel
        selectedSector={highlightSector}
        onSelectLeader={onSelectLeader}
        onAskSector={onAskSector}
      />
      <ActionCenter onNavigate={onNavigate} onChatQuery={onChatQuery} />
    </>
  );
});

export type { FocusEmptyStateProps };
