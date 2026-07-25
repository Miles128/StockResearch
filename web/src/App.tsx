import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import {
  api,
  HoldingEnriched,
  LlmUsage,
  StockQuoteOut,
  WatchlistItem,
} from "./api";
import type { CopilotContext } from "./appTypes";
import type { CenterTab, FocusContext, ListsLayoutMode } from "./layoutTypes";
import { FocusTabBar } from "./FocusTabBar";
import { PriceConflictBanner } from "./PriceConflictBanner";
import { activeFocusContext, removeFocusTab, upsertFocusTab, type FocusTab } from "./focusTabs";
import { buildKnownSymbols } from "./copilotFocusSync";
import { ListsSidebar } from "./ListsSidebar";
import { HeaderSearch } from "./HeaderSearch";
import { PriceAlertBell } from "./PriceAlertBell";
import { SectorMoversPanel } from "./SectorMoversPanel";
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
import { useLlmInit } from "./hooks/useLlmInit";
import { useMarketOverview } from "./hooks/useMarketOverview";
import { useNews } from "./hooks/useNews";
import { usePortfolio } from "./hooks/usePortfolio";
import { useRiskCheckup } from "./hooks/useRiskCheckup";
import { useWatchlist } from "./hooks/useWatchlist";
import { DataSourceDetails } from "./DataSourceDetails";
import { DemoBanner } from "./DemoBanner";
import { BackendHealthBanner } from "./BackendHealthBanner";
import { ActionCenter } from "./ActionCenter";
import { HoldingTradeModal, type TradeDraft } from "./HoldingTradeModal";
import { useI18n } from "./i18n";
import { formatHeaderUsage, formatLlmUsage } from "./llmUsageFormat";
import { indexSymbolKey, localizeIndexName } from "./indexLabels";
import { MarketTicker } from "./MarketTicker";
import { MarketPanel } from "./MarketPanel";
import { NewsPanel } from "./NewsPanel";
import { computePortfolioSummary, computeSectorConcentration } from "./portfolioHelpers";
import { RiskPanel } from "./RiskPanel";
import { SettingsPanel } from "./SettingsPanel";
import { ModeSwitcher } from "./ModeSwitcher";
import { Onboarding } from "./Onboarding";
import {
  IconMessages,
  IconSettings,
  IconSignal,
} from "./ui/Icons";
import {
  READING_MODE_I18N_KEYS,
  switchMode,
  type AppMode,
} from "./modeSettings";

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
    v > excellent ? t("rating.excellent") : v > good ? t("rating.good") : v > 0 ? t("rating.fair") : t("rating.poor");

  const [centerTab, setCenterTab] = useState<CenterTab>("focus");
  const { layoutSettings, setLayoutSettings, startCopilotResize, startListsResize } = useLayoutResize();
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
  const focusContext = activeFocusContext(focusTabs, activeFocusTabId);
  const [highlightSector, setHighlightSector] = useState<string | null>(null);
  const [pageContext, setPageContext] = useState<CopilotContext | null>(null);
  const [error, setError] = useState("");
  const [dataDetailsOpen, setDataDetailsOpen] = useState(false);
  const [tradeModalOpen, setTradeModalOpen] = useState(false);
  const [tradeModalSeed, setTradeModalSeed] = useState<Partial<TradeDraft> | null>(null);
  const [inlineTradeOpen, setInlineTradeOpen] = useState(false);

  const showError = useCallback((msg: string) => {
    setError(msg);
    setTimeout(() => setError(""), 4000);
  }, []);

  const {
    marketOverview,
    overviewLoading,
    dataStatus,
    loadOverview,
    refreshDataStatus,
  } = useMarketOverview();
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

  function openFocus(context: FocusContext) {
    const next = upsertFocusTab(focusTabs, context);
    setFocusTabs(next.tabs);
    setActiveFocusTabId(next.activeId);
    setCenterTab("focus");
  }

  const knownSymbols = useMemo(
    () => buildKnownSymbols(holdings, watchlist),
    [holdings, watchlist],
  );

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

  const chatExamples = useMemo(() => {
    const all = {
      market: { label: t("chat.exampleMarketLabel"), query: t("chat.exampleMarketQuery") },
      stock: { label: t("chat.exampleStockLabel"), query: t("chat.exampleStockQuery") },
      news: { label: t("chat.exampleNewsLabel"), query: t("chat.exampleNewsQuery") },
      risk: { label: t("chat.exampleRiskLabel"), query: t("chat.exampleRiskQuery") },
      sentiment: { label: t("chat.exampleSentimentLabel"), query: t("chat.exampleSentimentQuery") },
      sector: { label: t("chat.exampleSectorLabel"), query: t("chat.exampleSectorQuery") },
      pnl: { label: t("chat.examplePnlLabel"), query: t("chat.examplePnlQuery") },
      topMover: { label: t("chat.exampleTopMoverLabel"), query: t("chat.exampleTopMoverQuery") },
      newsImpact: { label: t("chat.exampleNewsImpactLabel"), query: t("chat.exampleNewsImpactQuery") },
      topRisk: { label: t("chat.exampleTopRiskLabel"), query: t("chat.exampleTopRiskQuery") },
      stress: { label: t("chat.exampleStressLabel"), query: t("chat.exampleStressQuery") },
    };
    const byTab: Record<CenterTab, typeof all[keyof typeof all][]> = {
      focus: [all.stock, all.pnl, all.topMover, all.risk],
      market: [all.market, all.sentiment, all.sector, all.news],
      risk: [all.risk, all.topRisk, all.stress, all.pnl],
      news: [all.news, all.newsImpact, all.sentiment, all.market],
    };
    return byTab[centerTab];
  }, [t, locale, centerTab]);
  const portfolioSummary = useMemo(() => computePortfolioSummary(holdings), [holdings]);
  const sectorMix = useMemo(() => computeSectorConcentration(holdings), [holdings]);
  const marketSessionLabel =
    holdings[0]?.market_session === "trading" ? t("ticker.trading") : t("ticker.closed");
  const headerUsage = useMemo((): LlmUsage | null => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const m = messages[i];
      if (m.role === "assistant" && m.llmUsage && m.llmUsage.total_tokens > 0) {
        return m.llmUsage;
      }
    }
    return null;
  }, [messages]);

  function dataSourceLabel(): string {
    if (!dataStatus) return t("header.dataUnknown");
    const overview = dataStatus.overview;
    const quotes = dataStatus.quotes;
    const primary = overview?.primary || quotes?.primary || "sina";
    const fallback = overview?.fallback || quotes?.fallback || "akshare";
    const degraded = Boolean(overview?.degraded || quotes?.degraded);
    if (degraded) {
      return t("header.dataDegraded").replace("{primary}", primary).replace("{fallback}", fallback);
    }
    // 默认并列展示主源 + 备源，让用户看到完整源链路
    return t("header.dataLiveMulti").replace("{primary}", primary).replace("{fallback}", fallback);
  }

  function toggleLocale() {
    setLocale(locale === "zh" ? "en" : "zh");
  }

  function handleSwitchMode(mode: AppMode) {
    persistModeSettings(switchMode(modeSettings, mode));
  }

  useEffect(() => {
    // PRD §七: UI 轮询默认关。开启前不启动任何定时器。
    if (!modeSettings.uiPollingEnabled) return;
    let cancelled = false;
    let timeoutId = 0;
    const tradingPollMs = 30_000;
    const closedPollMs = Math.max(modeSettings.quoteRefreshMinutes, 1) * 60_000;

    async function refreshQuotes() {
      if (cancelled || document.hidden) {
        timeoutId = window.setTimeout(refreshQuotes, tradingPollMs);
        return;
      }
      try {
        const data = await loadHoldings({ silent: true });
        await refreshWatchlistQuotes({ silent: true });
        if (cancelled) return;
        const trading = data.some((h) => h.market_session === "trading");
        timeoutId = window.setTimeout(refreshQuotes, trading ? tradingPollMs : closedPollMs);
      } catch {
        if (!cancelled) {
          timeoutId = window.setTimeout(refreshQuotes, tradingPollMs);
        }
      }
    }

    timeoutId = window.setTimeout(refreshQuotes, tradingPollMs);
    return () => {
      cancelled = true;
      if (timeoutId) window.clearTimeout(timeoutId);
    };
  }, [loadHoldings, refreshWatchlistQuotes, modeSettings.quoteRefreshMinutes, modeSettings.uiPollingEnabled]);

  useEffect(() => {
    setFocusTabs((tabs) => {
      let changed = false;
      const next = tabs.map((tab) => {
        if (tab.context.kind !== "stock") return tab;
        const sym = tab.context.symbol;
        const holding = holdings.find((h) => h.symbol === sym);
        const quote = watchlistQuotes[sym];
        const price = holding?.price ?? quote?.price ?? tab.context.price;
        const change_pct = holding?.change_pct ?? quote?.change_pct ?? tab.context.change_pct;
        if (price === tab.context.price && change_pct === tab.context.change_pct) return tab;
        changed = true;
        return { ...tab, context: { ...tab.context, price, change_pct } };
      });
      return changed ? next : tabs;
    });
  }, [holdings, watchlistQuotes]);

  function onTickerIndexClick(name: string) {
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
  }

  function askCopilot(
    query: string,
    context: CopilotContext,
    options?: { briefingKind?: "premarket" | "intraday" | "postmarket" },
  ) {
    setPageContext(context);
    setCopilotOpen(true);
    if (options?.briefingKind) {
      void runBriefingInCopilot(query, options.briefingKind);
      return;
    }
    if (!query.trim()) return;
    startChatQuery(query, { context });
  }

  function handleActionNavigate(target: string) {
    if (target === "risk") setCenterTab("risk");
    else if (target === "news") setCenterTab("news");
    else if (target === "market") setCenterTab("market");
    else {
      setCopilotOpen(true);
    }
  }

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

  function selectHolding(h: HoldingEnriched) {
    setHighlightSector(null);
    openFocus(holdingToStock(h));
  }

  function selectSymbol(symbol: string, name: string, quote?: StockQuoteOut) {
    setHighlightSector(null);
    openFocus({
      kind: "stock",
      symbol,
      name,
      price: quote?.price ?? null,
      change_pct: quote?.change_pct ?? null,
    });
  }

  function selectSector(name: string) {
    setHighlightSector(name);
    openFocus({ kind: "sector", name });
  }

  function selectWatchlistItem(item: WatchlistItem) {
    selectSymbol(item.symbol, item.name, watchlistQuotes[item.symbol]);
  }

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
      <div className="app-chrome">
        <div className="chrome-left">
          <span className="chrome-brand">StockResearch</span>
        </div>
        <HeaderSearch
          onSelectStock={(symbol, name) => selectSymbol(symbol, name)}
          onAskQuery={openCopilotQuery}
        />
        <MarketTicker
          inline
          overview={marketOverview}
          loading={overviewLoading}
          sessionLabel={marketSessionLabel}
          northboundLabel={t("ticker.northbound")}
          breadthLabel={t("ticker.breadth")}
          refreshTitle={t("ticker.refresh")}
          onRefresh={() => void loadOverview()}
          onIndexClick={onTickerIndexClick}
        />
        <div className="chrome-meta">
          <ModeSwitcher settings={modeSettings} onSwitch={handleSwitchMode} />
          <PriceAlertBell
            onSelectSymbol={(symbol, name) => selectSymbol(symbol, name)}
            pollingEnabled={modeSettings.uiPollingEnabled}
            pollingIntervalMs={modeSettings.quoteRefreshMinutes * 60_000}
          />
          {headerUsage && (
            <span className="chrome-usage" title={formatLlmUsage(headerUsage, t)}>
              {formatHeaderUsage(headerUsage, t)}
            </span>
          )}
          <button
            type="button"
            className={`icon-btn data-source-icon${dataStatus && (dataStatus.quotes?.degraded || dataStatus.overview?.degraded) ? " degraded" : ""}`}
            title={dataStatus?.overview?.message || dataStatus?.quotes?.message || dataSourceLabel()}
            onClick={() => setDataDetailsOpen(true)}
          >
            <IconSignal />
          </button>
          <button
            type="button"
            className="icon-btn"
            title={t("settings.readingModeCurrent", {
              reading: t(READING_MODE_I18N_KEYS[modeSettings.readingMode].short),
            })}
            onClick={() => setSetupOpen(true)}
            aria-label={t("header.settingsTitle")}
          >
            <IconSettings />
          </button>
          <button
            type="button"
            className="locale-toggle-btn"
            onClick={toggleLocale}
            title={locale === "zh" ? "English" : "中文"}
          >
            {locale === "zh" ? "En" : "中"}
          </button>
        </div>
      </div>
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
      {dataDetailsOpen && <DataSourceDetails status={dataStatus} onClose={() => setDataDetailsOpen(false)} />}
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
            {centerTab === "focus" && !focusContext && focusTabs.length === 0 && <BackendHealthBanner />}
            {centerTab === "focus" && !focusContext && focusTabs.length === 0 && holdings.length === 0 && !isDemo && (
              <DemoBanner onLoad={loadDemoHoldings} onClear={clearDemoHoldings} isDemo={isDemo} loading={demoLoading} />
            )}
            {centerTab === "focus" && !focusContext && focusTabs.length === 0 && isDemo && (
              <DemoBanner
                onLoad={loadDemoHoldings}
                onClear={clearDemoHoldings}
                onGoPortfolio={() => setCenterTab("focus")}
                isDemo={isDemo}
                loading={demoLoading}
              />
            )}

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
              <>
                <SectorMoversPanel
                  selectedSector={highlightSector}
                  onSelectLeader={(symbol, name) => selectSymbol(symbol, name)}
                  onAskSector={selectSector}
                />
                <ActionCenter
                  onNavigate={handleActionNavigate}
                  onChatQuery={(query) => {
                    const context: CopilotContext = {
                      kind: "focus",
                      label: locale === "zh" ? "我的持仓" : "My holdings",
                    };
                    setPageContext(context);
                    setCopilotOpen(true);
                    startChatQuery(query, { context });
                  }}
                />
              </>
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
