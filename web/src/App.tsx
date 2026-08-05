import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { api, HoldingEnriched, StockQuoteOut, WatchlistItem } from "./api";
import type { CopilotContext } from "./appTypes";
import type { CenterTab, FocusContext, ListsLayoutMode } from "./layoutTypes";
import { FocusTabBar } from "./FocusTabBar";
import { PriceConflictBanner } from "./PriceConflictBanner";
import { activeFocusContext, removeFocusTab, upsertFocusTab, type FocusTab } from "./focusTabs";
import { buildKnownSymbols } from "./copilotFocusSync";
import { ListsSidebar } from "./ListsSidebar";
import { StockFocusView } from "./StockFocusView";
import { ChatPanel } from "./ChatPanel";
import { CopilotPanel } from "./CopilotPanel";
import { GlossaryProvider } from "./GlossaryContext";
import { useAppBootstrap } from "./hooks/useAppBootstrap";
import { useChatExecution } from "./hooks/useChatExecution";
import { useCopilotThreads } from "./hooks/useCopilotThreads";
import { useLayoutResize } from "./hooks/useLayoutResize";
import {
  LISTS_DETAIL_WIDTH,
  LISTS_EXPAND_WIDTH,
  LISTS_WIDTH_MAX,
  saveLayoutSettings,
} from "./layoutSettings";
import { useChatExamples } from "./hooks/useChatExamples";
import { useFocusTabQuoteSync } from "./hooks/useFocusTabQuoteSync";
import { useLlmInit } from "./hooks/useLlmInit";
import { useMarketOverview } from "./hooks/useMarketOverview";
import { useNews } from "./hooks/useNews";
import { usePortfolio } from "./hooks/usePortfolio";
import { useRiskCheckup } from "./hooks/useRiskCheckup";
import { useQuotePolling } from "./hooks/useQuotePolling";
import { useWatchlist } from "./hooks/useWatchlist";
import { HoldingTradeModal, type TradeDraft } from "./HoldingTradeModal";
import { BatchResearchModal } from "./BatchResearchModal";
import { useI18n } from "./i18n";
import { indexSymbolKey, localizeIndexName } from "./indexLabels";
import { MarketPanel } from "./MarketPanel";
import { NewsPanel } from "./NewsPanel";
import { computePortfolioSummary, computeSectorConcentration } from "./portfolioHelpers";
import { RiskPanel } from "./RiskPanel";
import { SettingsPanel } from "./SettingsPanel";
import { Onboarding } from "./Onboarding";
import { PracticeBanner } from "./PracticeBanner";
import { IconMessages } from "./ui/Icons";
import { switchMode, type AppMode } from "./modeSettings";
import { AppHeader } from "./app/AppHeader";
import { FocusEmptyState } from "./app/FocusEmptyState";

export { ErrorBoundary } from "./app/ErrorBoundary";

export default function App() {
  const { t, locale, setLocale } = useI18n();
  const centerTabs = useMemo(
    () => [
      { key: "focus" as CenterTab, label: t("center.focus") },
      { key: "market" as CenterTab, label: t("center.market") },
      { key: "risk" as CenterTab, label: t("center.risk") },
      { key: "news" as CenterTab, label: t("center.news") },
    ],
    [t, locale],
  );
  const numLocale = locale === "zh" ? "zh-CN" : "en-US";
  const ratioGrade = (v: number, excellent: number, good: number) =>
    v > excellent
      ? t("rating.excellent")
      : v > good
        ? t("rating.good")
        : v > 0
          ? t("rating.fair")
          : t("rating.poor");

  const [centerTab, setCenterTab] = useState<CenterTab>("focus");
  const { layoutSettings, setLayoutSettings, startCopilotResize, startListsResize } =
    useLayoutResize();
  const [listsMode, setListsMode] = useState<ListsLayoutMode>("sidebar");

  const expandListsPanel = useCallback(() => {
    setListsMode("center");
    setLayoutSettings((prev) => {
      const listsWidth = Math.min(
        LISTS_WIDTH_MAX,
        Math.max(LISTS_EXPAND_WIDTH, LISTS_DETAIL_WIDTH),
      );
      const next = { ...prev, listsWidth };
      saveLayoutSettings(next);
      return next;
    });
  }, [setLayoutSettings]);
  const [copilotOpen, setCopilotOpen] = useState(true);
  const [focusTabs, setFocusTabs] = useState<FocusTab[]>([]);
  const [activeFocusTabId, setActiveFocusTabId] = useState<string | null>(null);
  const [practiceDismissed, setPracticeDismissed] = useState(
    () => localStorage.getItem("advisor_practice_done") === "1",
  );
  const focusContext = activeFocusContext(focusTabs, activeFocusTabId);
  const [highlightSector, setHighlightSector] = useState<string | null>(null);
  const [pageContext, setPageContext] = useState<CopilotContext | null>(null);
  const [error, setError] = useState("");
  const [tradeModalOpen, setTradeModalOpen] = useState(false);
  const [batchResearchOpen, setBatchResearchOpen] = useState(false);
  const [tradeModalSeed, setTradeModalSeed] = useState<Partial<TradeDraft> | null>(null);
  const [inlineTradeOpen, setInlineTradeOpen] = useState(false);

  const showError = useCallback((msg: string) => {
    setError(msg);
    setTimeout(() => setError(""), 4000);
  }, []);

  const { marketOverview, overviewLoading, dataStatus, loadOverview, refreshDataStatus } =
    useMarketOverview();
  const {
    llmConfigured,
    llmCheckDone,
    setupOpen,
    setSetupOpen,
    handleConfigured: handleLlmConfigured,
  } = useLlmInit();
  const {
    modeSettings,
    onboardingOpen,
    glossary,
    persistModeSettings,
    handleOnboardingComplete,
    handleOnboardingSkip,
  } = useAppBootstrap();
  const {
    holdings,
    holdingsLoading,
    holdingsRefreshing,
    isDemo,
    demoLoading,
    loadHoldings,
    loadDemoHoldings,
    clearDemoHoldings,
  } = usePortfolio(showError, refreshDataStatus);
  const {
    watchlist,
    watchlistQuotes,
    watchlistLoading,
    refreshWatchlistQuotes,
    addWatchlistItem,
    removeWatchlistItem,
  } = useWatchlist(showError);
  const { news, newsLoading, newsSectors, sectorSaving, loadNews, toggleNewsSector } = useNews(
    centerTab === "news" ||
      centerTab === "market" ||
      (centerTab === "focus" && focusContext != null),
    showError,
  );
  const { risk, riskLoading, riskStream, riskStatusMsg, runRisk } = useRiskCheckup(showError, t);
  const riskTabRunRef = useRef(false);

  useEffect(() => {
    if (centerTab !== "risk") {
      riskTabRunRef.current = false;
      return;
    }
    if (holdingsLoading || holdings.length === 0 || riskTabRunRef.current) return;
    riskTabRunRef.current = true;
    void runRisk();
  }, [centerTab, holdings.length, holdingsLoading, runRisk]);
  const {
    threads: copilotThreads,
    activeId: activeThreadId,
    messages,
    sessionId,
    input,
    setInput,
    chatStream,
    setChatStream,
    switchThread,
    newThread: newCopilotThread,
    deleteThread,
    appendMessages,
    setSessionId,
    prepareUserTurn,
  } = useCopilotThreads({ defaultTitle: t("copilot.untitledThread") });

  const settingsRequired = llmCheckDone && !llmConfigured;

  const openFocus = useCallback(
    (context: FocusContext) => {
      const next = upsertFocusTab(focusTabs, context);
      setFocusTabs(next.tabs);
      setActiveFocusTabId(next.activeId);
      setCenterTab("focus");
    },
    [focusTabs],
  );

  const knownSymbols = useMemo(() => buildKnownSymbols(holdings, watchlist), [holdings, watchlist]);

  const chat = useChatExecution({
    t,
    locale,
    sessionId,
    setSessionId,
    pageContext,
    focusContext,
    knownSymbols,
    appendMessages,
    prepareUserTurn,
    input,
    setInput,
    setChatStream,
    setFocusTabs,
    setActiveFocusTabId,
    setCenterTab,
    setCopilotOpen,
    setPageContext,
    openFocus,
  });

  const {
    chatLoading,
    statusMsg,
    startChatQuery,
    sendChat,
    analyzeHolding,
    runBriefingInCopilot,
    confirmChatStock,
    confirmChatRoute,
    openCopilotQuery,
  } = chat;

  const chatExamples = useChatExamples(t, locale, centerTab);
  const portfolioSummary = useMemo(() => computePortfolioSummary(holdings), [holdings]);
  const sectorMix = useMemo(() => computeSectorConcentration(holdings), [holdings]);
  const marketSessionLabel =
    holdings[0]?.market_session === "trading" ? t("ticker.trading") : t("ticker.closed");

  const toggleLocale = useCallback(() => {
    setLocale(locale === "zh" ? "en" : "zh");
  }, [locale, setLocale]);

  const handleSwitchMode = useCallback(
    (mode: AppMode) => {
      persistModeSettings(switchMode(modeSettings, mode));
    },
    [modeSettings, persistModeSettings],
  );

  const refreshOverview = useCallback(() => {
    void loadOverview();
  }, [loadOverview]);

  const openSettings = useCallback(() => {
    setSetupOpen(true);
  }, [setSetupOpen]);

  const goPortfolio = useCallback(() => {
    setCenterTab("focus");
  }, []);

  useQuotePolling({
    enabled: modeSettings.uiPollingEnabled,
    quoteRefreshMinutes: modeSettings.quoteRefreshMinutes,
    loadHoldings,
    refreshWatchlistQuotes,
  });

  useFocusTabQuoteSync(setFocusTabs, holdings, watchlistQuotes);

  const onTickerIndexClick = useCallback(
    (name: string) => {
      setCenterTab("focus");
      const match = marketOverview?.indices.find(
        (idx) => localizeIndexName(idx.symbol, idx.name, t) === name,
      );
      if (match) {
        const symbol = indexSymbolKey(match.symbol, match.name);
        if (symbol) {
          openFocus({
            kind: "index",
            symbol,
            name: localizeIndexName(match.symbol, match.name, t),
          });
        }
      }
    },
    [marketOverview, t, openFocus],
  );

  const askCopilot = useCallback(
    (
      query: string,
      context: CopilotContext,
      options?: { briefingKind?: "premarket" | "intraday" | "postmarket" },
    ) => {
      setPageContext(context);
      setCopilotOpen(true);
      if (options?.briefingKind) {
        void runBriefingInCopilot(query, options.briefingKind);
        return;
      }
      if (!query.trim()) return;
      startChatQuery(query, { context });
    },
    [runBriefingInCopilot, startChatQuery],
  );

  const handleActionNavigate = useCallback((target: string) => {
    if (target === "risk") setCenterTab("risk");
    else if (target === "news") setCenterTab("news");
    else if (target === "market") setCenterTab("market");
    else {
      setCopilotOpen(true);
    }
  }, []);

  function holdingToStock(h: HoldingEnriched): FocusContext {
    return {
      kind: "stock",
      symbol: h.symbol,
      name: h.name,
      price: h.price,
      change_pct: h.change_pct,
    };
  }

  const focusSymbol = focusContext?.kind === "stock" ? focusContext.symbol : null;

  function closeFocusTab(tabId: string) {
    const next = removeFocusTab(focusTabs, tabId);
    setFocusTabs(next.tabs);
    setActiveFocusTabId(next.activeId);
  }

  useEffect(() => {
    if (focusContext?.kind === "stock") {
      setPageContext({
        kind: "stock",
        label: `${focusContext.name} ${focusContext.symbol}`,
        detail: focusContext.symbol,
      });
      return;
    }
    if (focusContext?.kind === "index") {
      setPageContext({
        kind: "focus",
        label: focusContext.name,
        detail: focusContext.symbol,
      });
      return;
    }
    if (focusContext?.kind === "sector") {
      setPageContext({
        kind: "focus",
        label: focusContext.name,
        detail: `板块：${focusContext.name}`,
      });
      return;
    }
    if (centerTab === "risk") {
      setPageContext({ kind: "risk", label: t("center.risk") });
      return;
    }
    if (centerTab === "news") {
      setPageContext({ kind: "news", label: t("center.news") });
      return;
    }
    if (centerTab === "market") {
      setPageContext({ kind: "focus", label: t("center.market") });
      return;
    }
    setPageContext({ kind: "focus", label: t("center.focus") });
  }, [centerTab, focusContext, t, locale]);

  const selectHolding = useCallback(
    (h: HoldingEnriched) => {
      setHighlightSector(null);
      openFocus(holdingToStock(h));
    },
    [openFocus],
  );

  const selectSymbol = useCallback(
    (symbol: string, name: string, quote?: StockQuoteOut) => {
      setHighlightSector(null);
      openFocus({
        kind: "stock",
        symbol,
        name,
        price: quote?.price ?? null,
        change_pct: quote?.change_pct ?? null,
      });
    },
    [openFocus],
  );

  const selectSector = useCallback(
    (name: string) => {
      setHighlightSector(name);
      openFocus({ kind: "sector", name });
    },
    [openFocus],
  );

  const selectWatchlistItem = useCallback(
    (item: WatchlistItem) => {
      selectSymbol(item.symbol, item.name, watchlistQuotes[item.symbol]);
    },
    [selectSymbol, watchlistQuotes],
  );

  const holdingsChatQuery = useCallback(
    (query: string) => {
      const context: CopilotContext = {
        kind: "focus",
        label: locale === "zh" ? "我的持仓" : "My holdings",
      };
      setPageContext(context);
      setCopilotOpen(true);
      startChatQuery(query, { context });
    },
    [locale, startChatQuery],
  );

  function openAddHoldingModal() {
    setInlineTradeOpen(true);
  }

  function closeInlineTrade() {
    setInlineTradeOpen(false);
  }

  function openEditHoldingModal(h: HoldingEnriched) {
    setTradeModalSeed({
      side: "sell",
      symbol: h.symbol,
      name: h.name,
      query: h.name,
      lots: "1",
    });
    setTradeModalOpen(true);
  }

  function closeTradeModal() {
    setTradeModalOpen(false);
    setTradeModalSeed(null);
  }

  function analyzeFocusedStock() {
    if (!focusContext || focusContext.kind !== "stock") return;
    const holding = holdings.find((h) => h.symbol === focusContext.symbol);
    if (holding) {
      analyzeHolding(holding);
      return;
    }
    openCopilotQuery(`分析${focusContext.name}（${focusContext.symbol}）`);
  }

  function alertHoldingTags(message: string): HoldingEnriched[] {
    return holdings.filter((h) => message.includes(h.name) || message.includes(h.symbol));
  }

  async function deleteHolding(id: number) {
    try {
      await api.deleteHolding(id);
      await loadHoldings();
    } catch (e) {
      showError(String(e));
    }
  }

  return (
    <GlossaryProvider
      enabled={modeSettings.mode === "advisor" && modeSettings.enableGlossary}
      terms={glossary}
    >
      <div className="app-shell" data-mode={modeSettings.mode}>
        <AppHeader
          t={t}
          locale={locale}
          overview={marketOverview}
          overviewLoading={overviewLoading}
          sessionLabel={marketSessionLabel}
          modeSettings={modeSettings}
          onSelectStock={selectSymbol}
          onAskQuery={openCopilotQuery}
          onRefreshOverview={refreshOverview}
          onIndexClick={onTickerIndexClick}
          onSwitchMode={handleSwitchMode}
          onOpenSettings={openSettings}
          onToggleLocale={toggleLocale}
        />
        <PriceConflictBanner conflicts={dataStatus?.price_conflicts ?? []} />
        <SettingsPanel
          open={setupOpen}
          onClose={() => {
            if (!settingsRequired) setSetupOpen(false);
          }}
          required={settingsRequired}
          onConfigured={handleLlmConfigured}
          onModeSettingsChange={persistModeSettings}
          variant="modal"
        />
        {onboardingOpen && (
          <Onboarding onComplete={handleOnboardingComplete} onSkip={handleOnboardingSkip} />
        )}
        <HoldingTradeModal
          open={tradeModalOpen}
          holdings={holdings}
          onClose={closeTradeModal}
          onApplied={async () => {
            await loadHoldings();
          }}
          initialRow={tradeModalSeed}
        />
        {batchResearchOpen && (
          <BatchResearchModal
            symbols={watchlist.map((w) => w.symbol)}
            appMode={modeSettings.mode}
            onClose={() => setBatchResearchOpen(false)}
          />
        )}

        <div
          className={`app-body tri-shell lists-${listsMode}${!copilotOpen ? " copilot-collapsed" : ""}${settingsRequired ? " app-locked" : ""}`}
          style={
            {
              "--lists-w": listsMode === "hidden" ? "0px" : `${layoutSettings.listsWidth}px`,
              "--copilot-w": `${layoutSettings.copilotWidth}px`,
            } as CSSProperties
          }
        >
          {listsMode !== "hidden" && (
            <ListsSidebar
              mode={listsMode}
              onSetMode={setListsMode}
              onExpandLists={expandListsPanel}
              holdings={holdings}
              holdingsLoading={holdingsLoading}
              holdingsRefreshing={holdingsRefreshing}
              portfolioSummary={portfolioSummary}
              sectorMix={sectorMix}
              numLocale={numLocale}
              selectedSymbol={focusSymbol}
              onSelectHolding={selectHolding}
              onAddHolding={openAddHoldingModal}
              onEditHolding={openEditHoldingModal}
              onDeleteHolding={(id) => void deleteHolding(id)}
              inlineTradeOpen={inlineTradeOpen}
              onInlineTradeClose={closeInlineTrade}
              onTradeApplied={async () => {
                await loadHoldings();
              }}
              watchlist={watchlist}
              watchlistQuotes={watchlistQuotes}
              watchlistLoading={watchlistLoading}
              onSelectWatchlist={selectWatchlistItem}
              onAddWatchlist={addWatchlistItem}
              onRemoveWatchlist={(id) => void removeWatchlistItem(id)}
              onBatchResearch={() => setBatchResearchOpen(true)}
              onListsResizeStart={startListsResize}
              listsWidth={layoutSettings.listsWidth}
            />
          )}

          {listsMode === "hidden" && (
            <button
              type="button"
              className="panel-float-toggle lists-float-toggle"
              onClick={() => expandListsPanel()}
              title={t("lists.expandCenter")}
              aria-label={t("lists.expandCenter")}
            >
              »
            </button>
          )}

          <div className="center-column">
            <nav className="center-tabs" aria-label={t("center.aria")}>
              {centerTabs.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`center-tab${centerTab === item.key ? " active" : ""}`}
                  onClick={() => setCenterTab(item.key)}
                >
                  {item.label}
                </button>
              ))}
              {focusTabs.length > 0 && (
                <FocusTabBar
                  tabs={focusTabs}
                  activeId={centerTab === "focus" ? activeFocusTabId : null}
                  onSelect={(tabId) => {
                    setCenterTab("focus");
                    setActiveFocusTabId(tabId);
                  }}
                  onClose={closeFocusTab}
                />
              )}
            </nav>

            <div className="center-scroll">
              {error && <div className="error">{error}</div>}

              {centerTab === "focus" && focusContext && (
                <StockFocusView
                  focus={focusContext}
                  news={news}
                  newsLoading={newsLoading}
                  onAnalyze={analyzeFocusedStock}
                  onLoadNews={() => void loadNews()}
                />
              )}

              {centerTab === "focus" && !focusContext && focusTabs.length === 0 && (
                <FocusEmptyState
                  holdingsCount={holdings.length}
                  holdings={holdings}
                  watchlistCount={watchlist.length}
                  portfolioSummary={portfolioSummary}
                  isDemo={isDemo}
                  demoLoading={demoLoading}
                  highlightSector={highlightSector}
                  onLoadDemo={loadDemoHoldings}
                  onClearDemo={clearDemoHoldings}
                  onGoPortfolio={goPortfolio}
                  onSelectLeader={selectSymbol}
                  onAskSector={selectSector}
                  onNavigate={handleActionNavigate}
                  onChatQuery={holdingsChatQuery}
                />
              )}

              {centerTab === "market" && (
                <MarketPanel
                  overview={marketOverview}
                  overviewLoading={overviewLoading}
                  onRefreshOverview={() => void loadOverview()}
                  news={news}
                  newsLoading={newsLoading}
                  onLoadNews={() => void loadNews()}
                  onIndexClick={onTickerIndexClick}
                  onSectorClick={selectSector}
                  onAskCopilot={(query) =>
                    askCopilot(query, {
                      kind: "focus",
                      label: locale === "zh" ? "市场" : "Market",
                    })
                  }
                />
              )}

              {centerTab === "risk" && (
                <RiskPanel
                  holdings={holdings}
                  risk={risk}
                  loading={riskLoading}
                  riskStream={riskStream}
                  riskStatusMsg={riskStatusMsg}
                  numLocale={numLocale}
                  appMode={modeSettings.mode}
                  riskTolerance={modeSettings.riskTolerance}
                  monthlyIncome={modeSettings.monthlyIncome}
                  ratioGrade={ratioGrade}
                  alertHoldingTags={alertHoldingTags}
                  onRunRisk={() => void runRisk()}
                  onGoPortfolio={() => setCenterTab("focus")}
                  onAskCopilot={(query) =>
                    askCopilot(query, {
                      kind: "risk",
                      label: locale === "zh" ? "风控体检" : "Risk checkup",
                    })
                  }
                />
              )}

              {centerTab === "news" && (
                <NewsPanel
                  news={news}
                  newsLoading={newsLoading}
                  newsSectors={newsSectors}
                  sectorSaving={sectorSaving}
                  onLoadNews={() => void loadNews()}
                  onToggleSector={(s) => void toggleNewsSector(s)}
                  onAskCopilot={(query) =>
                    askCopilot(query, {
                      kind: "news",
                      label: locale === "zh" ? "新闻·研报" : "News",
                    })
                  }
                />
              )}
            </div>
          </div>

          {!copilotOpen && (
            <button
              type="button"
              className="panel-float-toggle copilot-float-toggle"
              onClick={() => setCopilotOpen(true)}
              title={t("copilot.expand")}
              aria-label={t("copilot.expand")}
            >
              <IconMessages />
            </button>
          )}
          {copilotOpen && (
            <aside className="copilot-column">
              <CopilotPanel
                open
                threads={copilotThreads}
                activeThreadId={activeThreadId}
                userContext={pageContext}
                onCollapsePanel={() => setCopilotOpen(false)}
                onNewThread={newCopilotThread}
                onSelectThread={switchThread}
                onDeleteThread={deleteThread}
                onResizeStart={startCopilotResize}
              >
                {modeSettings.mode === "advisor" &&
                  modeSettings.onboarded &&
                  !practiceDismissed && (
                    <PracticeBanner
                      onStart={() => {
                        localStorage.setItem("advisor_practice_done", "1");
                        setPracticeDismissed(true);
                        startChatQuery(
                          "帮我分析一下贵州茅台（600519），用大白话讲清楚结论、原因和风险",
                        );
                      }}
                      onDismiss={() => {
                        localStorage.setItem("advisor_practice_done", "1");
                        setPracticeDismissed(true);
                      }}
                    />
                  )}
                <ChatPanel
                  messages={messages}
                  loading={chatLoading}
                  statusMsg={statusMsg}
                  chatStream={chatStream}
                  input={input}
                  onInputChange={setInput}
                  chatExamples={chatExamples}
                  holdings={holdings}
                  appMode={modeSettings.mode}
                  onStartQuery={(query) => startChatQuery(query)}
                  onSend={sendChat}
                  onAnalyzeHolding={analyzeHolding}
                  onConfirmStock={confirmChatStock}
                  onConfirmRoute={confirmChatRoute}
                />
              </CopilotPanel>
            </aside>
          )}
        </div>
      </div>
    </GlossaryProvider>
  );
}
