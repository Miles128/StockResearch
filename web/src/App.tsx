import { Component, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ErrorInfo, type ReactNode } from "react";
import {
  api,
  AgentStreamEvent,
  ChatStreamOptions,
  ExecutionPreference,
  DataSourceStatus,
  HoldingEnriched,
  LlmUsage,
  GlossaryTerm,
  MarketOverview,
  NewsItem,
  RiskCheckup,
  SectorPreferences,
  StockQuoteOut,
  WatchlistItem,
} from "./api";
import type { CopilotContext, Message } from "./appTypes";
import type { CenterTab, FocusContext, ListsLayoutMode } from "./layoutTypes";
import { FocusTabBar } from "./FocusTabBar";
import { PriceConflictBanner } from "./PriceConflictBanner";
import { activeFocusContext, removeFocusTab, upsertFocusTab, type FocusTab } from "./focusTabs";
import { syncFocusTabsFromChat, buildKnownSymbols } from "./copilotFocusSync";
import { ListsSidebar } from "./ListsSidebar";
import { HeaderSearch } from "./HeaderSearch";
import { PriceAlertBell } from "./PriceAlertBell";
import { SectorMoversPanel } from "./SectorMoversPanel";
import { StockFocusView } from "./StockFocusView";
import { copilotContextToPayload } from "./chatContext";
import { ChatPanel } from "./ChatPanel";
import { CopilotPanel } from "./CopilotPanel";
import { GlossaryProvider } from "./GlossaryContext";
import { useCopilotThreads } from "./hooks/useCopilotThreads";
import { DataSourceDetails } from "./DataSourceDetails";
import { DemoBanner } from "./DemoBanner";
import { BackendHealthBanner } from "./BackendHealthBanner";
import { ActionCenter } from "./ActionCenter";
import { HoldingTradeModal, type TradeDraft } from "./HoldingTradeModal";
import { useI18n } from "./i18n";
import { isLlmConfiguredLocally, isServerLlmConfigured } from "./llmSettings";
import { formatHeaderUsage, formatLlmUsage } from "./llmUsageFormat";
import { indexSymbolKey, localizeIndexName } from "./indexLabels";
import { MarketTicker } from "./MarketTicker";
import { NewsPanel } from "./NewsPanel";
import { computePortfolioSummary, computeSectorConcentration } from "./portfolioHelpers";
import { RiskPanel } from "./RiskPanel";
import { SettingsPanel } from "./SettingsPanel";
import { stripDisclaimer } from "./disclaimerText";
import { hasProcessContent } from "./ProcessTrail";
import { seedGlossaryCache } from "./TermPopover";
import { applyStreamEvent, emptyStreamState } from "./streamEvents";
import { normalizeStreamEvent } from "./streamI18n";
import { formatBriefingMarkdown, localizeBriefing } from "./uiLabels";
import { ModeSwitcher } from "./ModeSwitcher";
import { Onboarding } from "./Onboarding";
import { AssetAllocationPanel } from "./AssetAllocationPanel";
import {
  IconMessages,
  IconSettings,
  IconSignal,
} from "./ui/Icons";
import {
  loadModeSettings,
  modeSettingsFromApiPayload,
  modeSettingsToApiPayload,
  READING_MODE_I18N_KEYS,
  saveModeSettings,
  switchMode,
  type AppMode,
  type ModeSettings,
} from "./modeSettings";
import {
  loadLayoutSettings,
  saveLayoutSettings,
  type LayoutSettings,
} from "./layoutSettings";

export class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24, color: "#ff6b6b", fontFamily: "monospace" }}>
          <h2>Something went wrong</h2>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{this.state.error?.message}</pre>
          <button onClick={() => this.setState({ hasError: false, error: null })} style={{ marginTop: 12, padding: "6px 16px" }}>
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const { t, locale, setLocale } = useI18n();
  const centerTabs = useMemo(
    () => [
      { key: "focus" as CenterTab, label: t("center.focus") },
      { key: "risk" as CenterTab, label: t("center.risk") },
      { key: "news" as CenterTab, label: t("center.news") },
    ],
    [t, locale],
  );
  const numLocale = locale === "zh" ? "zh-CN" : "en-US";
  const ratioGrade = (v: number, excellent: number, good: number) =>
    v > excellent ? t("rating.excellent") : v > good ? t("rating.good") : v > 0 ? t("rating.fair") : t("rating.poor");

  const [centerTab, setCenterTab] = useState<CenterTab>("focus");
  const [layoutSettings, setLayoutSettings] = useState<LayoutSettings>(() => loadLayoutSettings());
  const [listsMode, setListsMode] = useState<ListsLayoutMode>("sidebar");
  const [copilotOpen, setCopilotOpen] = useState(true);
  const [focusTabs, setFocusTabs] = useState<FocusTab[]>([]);
  const [activeFocusTabId, setActiveFocusTabId] = useState<string | null>(null);
  const focusContext = activeFocusContext(focusTabs, activeFocusTabId);
  const [highlightSector, setHighlightSector] = useState<string | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [watchlistQuotes, setWatchlistQuotes] = useState<Record<string, StockQuoteOut>>({});
  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [pageContext, setPageContext] = useState<CopilotContext | null>(null);
  const {
    threads: copilotThreads,
    activeId: activeThreadId,
    activeThread,
    messages,
    sessionId,
    input,
    setInput,
    chatStream,
    setChatStream,
    switchThread,
    newThread: newCopilotThread,
    renameThread: _renameThread,
    deleteThread,
    appendMessages,
    setSessionId,
  } = useCopilotThreads({ defaultTitle: t("copilot.untitledThread") });
  const [chatLoading, setChatLoading] = useState(false);
  const [riskLoading, setRiskLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [news, setNews] = useState<NewsItem[]>([]);
  const [holdings, setHoldings] = useState<HoldingEnriched[]>([]);
  const [holdingsLoading, setHoldingsLoading] = useState(false);
  const [risk, setRisk] = useState<RiskCheckup | null>(null);
  const [error, setError] = useState("");
  const [newsLoading, setNewsLoading] = useState(false);
  const [dataStatus, setDataStatus] = useState<DataSourceStatus | null>(null);
  const [llmConfigured, setLlmConfigured] = useState(false);
  const [llmCheckDone, setLlmCheckDone] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const [dataDetailsOpen, setDataDetailsOpen] = useState(false);
  const [marketOverview, setMarketOverview] = useState<MarketOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [newsSectors, setNewsSectors] = useState<SectorPreferences | null>(null);
  const [sectorSaving, setSectorSaving] = useState(false);
  const [isDemo, setIsDemo] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const autoDemoLoadRequested = useRef(false);
  const [modeSettings, setModeSettings] = useState<ModeSettings>(() => loadModeSettings());
  const [onboardingOpen, setOnboardingOpen] = useState(() => !loadModeSettings().onboarded);
  const [glossary, setGlossary] = useState<Record<string, GlossaryTerm>>({});
  const [tradeModalOpen, setTradeModalOpen] = useState(false);
  const [tradeModalSeed, setTradeModalSeed] = useState<Partial<TradeDraft> | null>(null);
  const [inlineTradeOpen, setInlineTradeOpen] = useState(false);
  const resizingRef = useRef(false);
  const resizingAxisRef = useRef<"copilot-x" | "lists" | "y">("copilot-x");
  const settingsRequired = llmCheckDone && !llmConfigured;

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!resizingRef.current) return;
      setLayoutSettings((prev) => {
        if (resizingAxisRef.current === "y") {
          const minH = 200;
          const maxH = window.innerHeight - 120;
          const next = window.innerHeight - e.clientY;
          return { ...prev, copilotHeight: Math.max(minH, Math.min(maxH, next)) };
        }
        if (resizingAxisRef.current === "lists") {
          const minW = 280;
          const maxW = Math.min(880, window.innerWidth - 480);
          const listsWidth = Math.max(minW, Math.min(maxW, e.clientX));
          return { ...prev, listsWidth };
        }
        const minW = 320;
        const maxW = Math.min(720, window.innerWidth - 400);
        const next = window.innerWidth - e.clientX;
        const copilotWidth = Math.max(minW, Math.min(maxW, next));
        return { ...prev, copilotWidth };
      });
    }
    function onUp() {
      if (!resizingRef.current) return;
      resizingRef.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      setLayoutSettings((prev) => {
        saveLayoutSettings(prev);
        return prev;
      });
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const chatExamples = useMemo(
    () => [
      { label: t("chat.exampleMarketLabel"), query: t("chat.exampleMarketQuery") },
      { label: t("chat.exampleStockLabel"), query: t("chat.exampleStockQuery") },
      { label: t("chat.exampleNewsLabel"), query: t("chat.exampleNewsQuery") },
      { label: t("chat.exampleRiskLabel"), query: t("chat.exampleRiskQuery") },
    ],
    [t, locale],
  );
  const portfolioSummary = useMemo(() => computePortfolioSummary(holdings), [holdings]);
  const sectorMix = useMemo(() => computeSectorConcentration(holdings), [holdings]);
  const knownSymbols = useMemo(
    () => buildKnownSymbols(holdings, watchlist),
    [holdings, watchlist],
  );
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

  function refreshDataStatus() {
    void api.dataSourceStatus().then(setDataStatus).catch(() => setDataStatus(null));
  }

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

  function handleLlmConfigured() {
    setLlmConfigured(true);
    setSetupOpen(false);
  }

  function toggleLocale() {
    setLocale(locale === "zh" ? "en" : "zh");
  }

  function persistModeSettings(next: ModeSettings) {
    setModeSettings(next);
    saveModeSettings(next);
    void api.saveModeSettings(modeSettingsToApiPayload(next)).catch(() => {
      // localStorage remains the startup cache if the API is temporarily unavailable.
    });
    void api
      .glossary()
      .then((list) => {
        const map: Record<string, GlossaryTerm> = {};
        for (const item of list) map[item.id] = item;
        seedGlossaryCache(map);
        setGlossary(map);
      })
      .catch(() => {});
  }

  function handleSwitchMode(mode: AppMode) {
    const next = switchMode(modeSettings, mode);
    persistModeSettings(next);
  }

  function handleOnboardingComplete(next: ModeSettings) {
    persistModeSettings(next);
    setOnboardingOpen(false);
  }

  function handleOnboardingSkip() {
    const next: ModeSettings = { ...modeSettings, onboarded: true };
    persistModeSettings(next);
    setOnboardingOpen(false);
  }

  async function loadOverview() {
    try {
      setOverviewLoading(true);
      setMarketOverview(await api.marketOverview());
      refreshDataStatus();
    } catch {
      setMarketOverview(null);
    } finally {
      setOverviewLoading(false);
    }
  }

  useEffect(() => {
    const cachedModeSettings = loadModeSettings();
    void api
      .modeSettings()
      .then((remote) => {
        const remoteSettings = modeSettingsFromApiPayload(remote);
        if (!remoteSettings.onboarded && cachedModeSettings.onboarded) {
          persistModeSettings(cachedModeSettings);
          setOnboardingOpen(false);
          return;
        }
        setModeSettings(remoteSettings);
        saveModeSettings(remoteSettings);
        setOnboardingOpen(!remoteSettings.onboarded);
      })
      .catch(() => {
        setModeSettings(cachedModeSettings);
        setOnboardingOpen(!cachedModeSettings.onboarded);
      });
    void api
      .glossary()
      .then((list) => {
        const map: Record<string, GlossaryTerm> = {};
        for (const item of list) map[item.id] = item;
        seedGlossaryCache(map);
        setGlossary(map);
      })
      .catch(() => setGlossary({}));
    void loadOverview();
    void loadWatchlist();
    void loadHoldings().then(() => {
      api.demoStatus().then((s) => setIsDemo(s.demo)).catch(() => {});
    });
    void api
      .llmSettings()
      .then((meta) => {
        const ok = isServerLlmConfigured(meta) || isLlmConfiguredLocally();
        setLlmConfigured(ok);
        setSetupOpen(!ok);
        setLlmCheckDone(true);
      })
      .catch(() => {
        const ok = isLlmConfiguredLocally();
        setLlmConfigured(ok);
        setSetupOpen(!ok);
        setLlmCheckDone(true);
      });
  }, []);

  useEffect(() => {
    if (centerTab !== "news") return;
    void api.newsSectors().then(setNewsSectors).catch(() => setNewsSectors(null));
    if (news.length === 0) void loadNews();
  }, [centerTab]);

  useEffect(() => {
    let timeoutId = 0;
    let cancelled = false;
    const watchSymbols = watchlist.map((i) => i.symbol).join(",");

    async function refreshWatchlistQuotes() {
      if (watchlist.length === 0) {
        setWatchlistQuotes({});
        return;
      }
      try {
        const quotes = await api.stockQuotes(watchlist.map((i) => i.symbol).join(","));
        const map: Record<string, StockQuoteOut> = {};
        for (const q of quotes) map[q.symbol] = q;
        setWatchlistQuotes(map);
      } catch {
        // keep last quotes on transient failures
      }
    }

    async function tick() {
      if (cancelled) return;
      let session: string | undefined;
      try {
        const data = await loadHoldings();
        await refreshWatchlistQuotes();
        const status = await api.dataSourceStatus();
        setDataStatus(status);
        session = status.quotes?.session ?? data[0]?.market_session;
      } catch {
        await refreshWatchlistQuotes();
      }
      if (!cancelled && session === "trading") {
        timeoutId = window.setTimeout(tick, 30_000);
      }
    }

    void tick();
    return () => {
      cancelled = true;
      if (timeoutId) window.clearTimeout(timeoutId);
    };
  }, [watchlist]);

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

  const showError = useCallback((msg: string) => {
    setError(msg);
    setTimeout(() => setError(""), 4000);
  }, []);

  async function loadHoldings(): Promise<HoldingEnriched[]> {
    try {
      setHoldingsLoading(true);
      const data = await api.holdingsEnriched();
      setHoldings(data);
      refreshDataStatus();
      if (data.length === 0 && !autoDemoLoadRequested.current) {
        autoDemoLoadRequested.current = true;
        try {
          await api.loadDemo();
          const demoData = await api.holdingsEnriched();
          setHoldings(demoData);
          setIsDemo(true);
          return demoData;
        } catch {
          // ignore auto-load failures
        }
      }
      return data;
    } catch (e) {
      showError(String(e));
      return holdings;
    } finally {
      setHoldingsLoading(false);
    }
  }

  async function executeChat(
    query: string,
    options?: ChatStreamOptions,
    contextOverride?: CopilotContext | null,
  ) {
    setChatLoading(true);
    setStatusMsg(t("chat.connecting"));
    setChatStream(emptyStreamState());
    let processSnapshot = emptyStreamState();
    const activeContext = contextOverride === undefined ? pageContext : contextOverride;
    const chatOptions: ChatStreamOptions = {
      ...options,
      userContext: activeContext ? copilotContextToPayload(activeContext) : null,
    };
    try {
      const resp = await api.chatStream(
        query,
        sessionId,
        (event: AgentStreamEvent) => {
          if (
            event.type === "analysis_choice" ||
            event.type === "stock_choice"
          ) {
            return;
          }
          const normalized = normalizeStreamEvent(event, t);
          setChatStream((prev) => {
            const next = applyStreamEvent(prev, normalized, t);
            processSnapshot = next;
            return next;
          });
          if (normalized.type === "status" && normalized.message) {
            setStatusMsg(normalized.message);
          }
        },
        chatOptions,
      );
      if (resp) {
        setSessionId(resp.session_id);
        processSnapshot = {
          ...processSnapshot,
          streamStatus: processSnapshot.streamStatus || statusMsg || t("chat.analysisDone"),
        };
        const assistantMsg: Message = {
          role: "assistant",
          content: stripDisclaimer(resp.reply),
          cards: resp.cards,
          intent: resp.intent,
          followUpQuestions: resp.follow_up_questions ?? [],
          llmUsage: resp.llm_usage ?? null,
          process: hasProcessContent(processSnapshot) ? processSnapshot : undefined,
        };
        appendMessages((m) => [...m, assistantMsg]);
        setFocusTabs((prevTabs) => {
          const synced = syncFocusTabsFromChat(query, resp, prevTabs, focusContext, knownSymbols);
          if (synced.activeId) {
            setActiveFocusTabId(synced.activeId);
            setCenterTab("focus");
            return synced.tabs;
          }
          return prevTabs;
        });
      }
    } catch {
      try {
        setStatusMsg(t("chat.streamFailed"));
        const resp = await api.chat(query, sessionId, chatOptions);
        setSessionId(resp.session_id);
        appendMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: stripDisclaimer(resp.reply),
            cards: resp.cards,
            intent: resp.intent,
            followUpQuestions: resp.follow_up_questions ?? [],
            llmUsage: resp.llm_usage ?? null,
          },
        ]);
        setFocusTabs((prevTabs) => {
          const synced = syncFocusTabsFromChat(query, resp, prevTabs, focusContext, knownSymbols);
          if (synced.activeId) {
            setActiveFocusTabId(synced.activeId);
            setCenterTab("focus");
            return synced.tabs;
          }
          return prevTabs;
        });
      } catch (e) {
        appendMessages((m) => [...m, { role: "assistant", content: `Error: ${String(e)}` }]);
      }
    } finally {
      setChatLoading(false);
      setStatusMsg("");
    }
  }

  function startChatQuery(
    query: string,
    opts?: { switchTab?: boolean; context?: CopilotContext | null },
  ) {
    if (!query.trim() || chatLoading) return;
    if (opts?.switchTab) setCopilotOpen(true);
    setInput("");
    appendMessages((m) => [...m, { role: "user", content: query }]);
    void executeChat(query, undefined, opts?.context);
  }

  function sendChat() {
    if (!input.trim() || chatLoading) return;
    startChatQuery(input.trim());
  }

  function analyzeHolding(h: HoldingEnriched) {
    const q = locale === "zh" ? `分析${h.name}` : `Analyze ${h.name}`;
    const context: CopilotContext = {
      kind: "stock",
      label: `${h.name} ${h.symbol}`,
      detail: `${h.sector} · ${h.quantity}股`,
    };
    setPageContext(context);
    setCopilotOpen(true);
    startChatQuery(q, { switchTab: true, context });
  }

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
    options?: { briefingKind?: "intraday" | "postmarket" },
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

  async function runBriefingInCopilot(userLabel: string, kind: "intraday" | "postmarket") {
    if (chatLoading) return;
    setInput("");
    setChatStream(emptyStreamState());
    appendMessages((m) => [...m, { role: "user", content: userLabel }]);
    setChatLoading(true);
    setStatusMsg(t("portfolio.briefingLoading"));
    try {
      const raw = await api.generateBriefing(kind);
      const briefing = localizeBriefing(raw, t);
      appendMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: formatBriefingMarkdown(briefing),
        },
      ]);
    } catch (e) {
      appendMessages((m) => [...m, { role: "assistant", content: `Error: ${String(e)}` }]);
    } finally {
      setChatLoading(false);
      setStatusMsg("");
    }
  }

  function handleActionNavigate(target: string) {
    if (target === "risk") setCenterTab("risk");
    else if (target === "news") setCenterTab("news");
    else {
      setCopilotOpen(true);
    }
  }

  async function loadWatchlist() {
    try {
      setWatchlistLoading(true);
      const items = await api.watchlist();
      setWatchlist(items);
      if (items.length === 0) {
        setWatchlistQuotes({});
        return;
      }
      const quotes = await api.stockQuotes(items.map((i) => i.symbol).join(","));
      const map: Record<string, StockQuoteOut> = {};
      for (const q of quotes) map[q.symbol] = q;
      setWatchlistQuotes(map);
    } catch (e) {
      showError(String(e));
    } finally {
      setWatchlistLoading(false);
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

  function openFocus(context: FocusContext) {
    const next = upsertFocusTab(focusTabs, context);
    setFocusTabs(next.tabs);
    setActiveFocusTabId(next.activeId);
    setCenterTab("focus");
  }

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
    if (centerTab === "risk") {
      setPageContext({ kind: "risk", label: t("center.risk") });
      return;
    }
    if (centerTab === "news") {
      setPageContext({ kind: "news", label: t("center.news") });
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

  async function addWatchlistItem(symbol: string, name: string) {
    try {
      await api.addWatchlist({ symbol, name });
      await loadWatchlist();
    } catch (e) {
      showError(String(e));
    }
  }

  async function removeWatchlistItem(id: number) {
    try {
      await api.deleteWatchlist(id);
      await loadWatchlist();
    } catch (e) {
      showError(String(e));
    }
  }

  function openCopilotQuery(query: string) {
    setCopilotOpen(true);
    startChatQuery(query);
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

  function handleCopilotResizeStart(axis: "x" | "y") {
    resizingRef.current = true;
    resizingAxisRef.current = axis === "y" ? "y" : "copilot-x";
    document.body.style.cursor = axis === "y" ? "row-resize" : "col-resize";
    document.body.style.userSelect = "none";
  }

  function handleListsResizeStart() {
    resizingRef.current = true;
    resizingAxisRef.current = "lists";
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }

  async function toggleNewsSector(sector: string) {
    if (!newsSectors || sectorSaving) return;
    const selected = newsSectors.selected.includes(sector)
      ? newsSectors.selected.filter((s) => s !== sector)
      : [...newsSectors.selected, sector];
    try {
      setSectorSaving(true);
      const updated = await api.updateNewsSectors(selected);
      setNewsSectors(updated);
      await api.ingestNews();
      setNews(await api.newsFeed());
    } catch (e) {
      showError(String(e));
    } finally {
      setSectorSaving(false);
    }
  }

  function alertHoldingTags(message: string): HoldingEnriched[] {
    return holdings.filter((h) => message.includes(h.name) || message.includes(h.symbol));
  }

  function confirmChatStock(originalMessage: string, symbol: string, name: string) {
    if (chatLoading) return;
    openFocus({ kind: "stock", symbol, name });
    appendMessages((m) => [...m, { role: "user", content: `${name}（${symbol}）` }]);
    void executeChat(originalMessage, { confirmedSymbol: symbol, confirmedName: name });
  }

  function confirmChatRoute(originalMessage: string, preference: ExecutionPreference) {
    if (chatLoading) return;
    const labels: Record<ExecutionPreference, string> = {
      react: t("chat.routeReact"),
      plan_execute: t("chat.routePlan"),
      preset: t("chat.routePreset"),
      auto: t("chat.routeAuto"),
    };
    appendMessages((m) => [
      ...m,
      { role: "user", content: t("chat.selectedMode", { mode: labels[preference] }) },
    ]);
    void executeChat(originalMessage, { executionPreference: preference });
  }

  async function loadDemoHoldings() {
    try {
      setDemoLoading(true);
      await api.loadDemo();
      setIsDemo(true);
      await loadHoldings();
    } catch (e) {
      showError(String(e));
    } finally {
      setDemoLoading(false);
    }
  }

  async function clearDemoHoldings() {
    try {
      setDemoLoading(true);
      await api.clearDemo();
      setIsDemo(false);
      await loadHoldings();
    } catch (e) {
      showError(String(e));
    } finally {
      setDemoLoading(false);
    }
  }

  async function loadNews() {
    try {
      setError("");
      setNewsLoading(true);
      await api.ingestNews();
      setNews(await api.newsFeed());
    } catch (e) {
      showError(String(e));
    } finally {
      setNewsLoading(false);
    }
  }

  async function runRisk() {
    try {
      setError("");
      setRiskLoading(true);
      setRisk(await api.riskCheckup());
    } catch (e) {
      showError(String(e));
    } finally {
      setRiskLoading(false);
    }
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
      <MarketTicker
        overview={marketOverview}
        loading={overviewLoading}
        sessionLabel={marketSessionLabel}
        northboundLabel={t("ticker.northbound")}
        breadthLabel={t("ticker.breadth")}
        refreshTitle={t("ticker.refresh")}
        onRefresh={() => void loadOverview()}
        onIndexClick={onTickerIndexClick}
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
            holdings={holdings}
            holdingsLoading={holdingsLoading}
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
            onListsResizeStart={handleListsResizeStart}
          />
        )}

        {listsMode === "hidden" && (
          <button
            type="button"
            className="panel-float-toggle lists-float-toggle"
            onClick={() => setListsMode("center")}
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

            {centerTab === "risk" && (
              <>
                {modeSettings.mode === "advisor" && (
                  <AssetAllocationPanel
                    riskTolerance={modeSettings.riskTolerance}
                    monthlyIncome={modeSettings.monthlyIncome}
                  />
                )}
                <RiskPanel
                  holdings={holdings}
                  risk={risk}
                  loading={riskLoading}
                  numLocale={numLocale}
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
              </>
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
              onResizeStart={handleCopilotResizeStart}
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
