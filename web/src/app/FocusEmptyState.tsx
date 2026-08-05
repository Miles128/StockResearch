import { memo } from "react";
import { ActionCenter } from "../ActionCenter";
import { BackendHealthBanner } from "../BackendHealthBanner";
import { DemoBanner } from "../DemoBanner";
import { PortfolioCockpit } from "../PortfolioCockpit";
import { SectorMoversPanel } from "../SectorMoversPanel";
import type { HoldingEnriched } from "../api";
import type { PortfolioSummary } from "../portfolioHelpers";

interface FocusEmptyStateProps {
  holdingsCount: number;
  watchlistCount: number;
  portfolioSummary: PortfolioSummary | null;
  holdings: HoldingEnriched[];
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

/**
 * Focus-tab landing state.
 *
 * 有持仓时 = 组合驾驶舱（组合日线 / 决策台账 / 组合事件）+ 板块异动与快讯（下沉）；
 * 无持仓时 = 引导横幅 + 板块异动 + 行动中心。
 */
export const FocusEmptyState = memo(function FocusEmptyState({
  holdingsCount,
  watchlistCount,
  portfolioSummary,
  holdings,
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
      {holdingsCount > 0 && (
        <PortfolioCockpit
          holdingsCount={holdingsCount}
          watchlistCount={watchlistCount}
          portfolioSummary={portfolioSummary}
          holdings={holdings}
          onSelectLeader={onSelectLeader}
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
