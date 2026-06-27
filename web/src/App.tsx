import { Component, useCallback, useEffect, useMemo, useRef, useState, type ErrorInfo, type ReactNode } from "react";
import {
  api,
  AgentStreamEvent,
  ChatStreamOptions,
  ExecutionPreference,
  DataSourceStatus,
  GlossaryTerm,
  HoldingEnriched,
  LlmUsage,
  MarketOverview,
  NewsItem,
  RiskCheckup,
  SectorPreferences,
  StockLookupOut,
} from "./api";
import type { CopilotContext, Message, Tab } from "./appTypes";
import { ChatPanel } from "./ChatPanel";
import { CanvasNav } from "./CanvasNav";
import { CopilotPanel } from "./CopilotPanel";
import { DataSourceDetails } from "./DataSourceDetails";
import { DemoBanner } from "./DemoBanner";
import { ActionCenter } from "./ActionCenter";
import { useI18n } from "./i18n";
import { isLlmConfiguredLocally, isServerLlmConfigured } from "./llmSettings";
import { formatHeaderUsage, formatLlmUsage } from "./llmUsageFormat";
import { MarketTicker } from "./MarketTicker";
import { MarketPanel } from "./MarketPanel";
import { NewsPanel } from "./NewsPanel";
import { computePortfolioSummary, computeSectorConcentration } from "./portfolioHelpers";
import { PortfolioPanel } from "./PortfolioPanel";
import { RiskPanel } from "./RiskPanel";
import { SettingsPanel } from "./SettingsPanel";
import { stripDisclaimer } from "./disclaimerText";
import { applyStreamEvent, emptyStreamState } from "./streamEvents";
import { normalizeStreamEvent } from "./streamI18n";
import { ModeSwitcher } from "./ModeSwitcher";
import { Onboarding } from "./Onboarding";
import { AssetAllocationPanel } from "./AssetAllocationPanel";
import {
  loadModeSettings,
  modeSettingsFromApiPayload,
  modeSettingsToApiPayload,
  saveModeSettings,
  switchMode,
  type AppMode,
  type ModeSettings,
} from "./modeSettings";

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
  const navItems = useMemo(
    () => [
      { key: "portfolio" as Tab, label: t("nav.portfolio") },
      { key: "risk" as Tab, label: t("nav.risk") },
      { key: "market" as Tab, label: t("nav.market") },
      { key: "news" as Tab, label: t("nav.news") },
    ],
    [t, locale],
  );
  const numLocale = locale === "zh" ? "zh-CN" : "en-US";
  const ratioGrade = (v: number, excellent: number, good: number) =>
    v > excellent ? t("rating.excellent") : v > good ? t("rating.good") : v > 0 ? t("rating.fair") : t("rating.poor");

  const [tab, setTab] = useState<Tab>("portfolio");
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [pageContext, setPageContext] = useState<CopilotContext | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [chatLoading, setChatLoading] = useState(false);
  const [riskLoading, setRiskLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [chatStream, setChatStream] = useState(emptyStreamState());
  const [news, setNews] = useState<NewsItem[]>([]);
  const [holdings, setHoldings] = useState<HoldingEnriched[]>([]);
  const [holdingsLoading, setHoldingsLoading] = useState(false);
  const [risk, setRisk] = useState<RiskCheckup | null>(null);
  const [error, setError] = useState("");
  const [holdingInput, setHoldingInput] = useState("");
  const [holdingCost, setHoldingCost] = useState("");
  const [holdingLots, setHoldingLots] = useState("");
  const [holdingDate, setHoldingDate] = useState("");
  const [lookupResult, setLookupResult] = useState<StockLookupOut | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [newsLoading, setNewsLoading] = useState(false);
  const [clock, setClock] = useState("");
  const [llmConfigured, setLlmConfigured] = useState(false);
  const [llmCheckDone, setLlmCheckDone] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const [dataDetailsOpen, setDataDetailsOpen] = useState(false);
  const [dataStatus, setDataStatus] = useState<DataSourceStatus | null>(null);
  const [marketOverview, setMarketOverview] = useState<MarketOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [lookupPrice, setLookupPrice] = useState<number | null>(null);
  const [newsSectors, setNewsSectors] = useState<SectorPreferences | null>(null);
  const [sectorSaving, setSectorSaving] = useState(false);
  const [isDemo, setIsDemo] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const autoDemoLoadRequested = useRef(false);
  const [modeSettings, setModeSettings] = useState<ModeSettings>(() => loadModeSettings());
  const [glossary, setGlossary] = useState<Record<string, GlossaryTerm>>({});
  const [onboardingOpen, setOnboardingOpen] = useState(() => !loadModeSettings().onboarded);
  const settingsRequired = llmCheckDone && !llmConfigured;

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
    if (dataStatus.use_mock) return t("header.dataMock");
    const overview = dataStatus.overview;
    const quotes = dataStatus.quotes;
    const primary = overview?.primary || quotes?.primary || "sina";
    const fallback = overview?.fallback || quotes?.fallback;
    const degraded = Boolean(overview?.degraded || quotes?.degraded);
    if (degraded && fallback) {
      return t("header.dataDegraded").replace("{primary}", primary).replace("{fallback}", fallback);
    }
    return t("header.dataLive").replace("{primary}", primary);
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

  useEffect(() => {
    const localeTag = locale === "zh" ? "zh-CN" : "en-US";
    const tick = () => {
      const now = new Date();
      const dateStr = now.toLocaleDateString(localeTag, {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      });
      const timeStr = now.toLocaleTimeString(localeTag, { hour12: false });
      setClock(`${dateStr} ${timeStr}`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [locale]);

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
    void api.glossary().then(setGlossary).catch(() => setGlossary({}));
    void loadOverview();
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
    if (tab !== "news") return;
    void api.newsSectors().then(setNewsSectors).catch(() => setNewsSectors(null));
    if (news.length === 0) void loadNews();
  }, [tab]);

  useEffect(() => {
    if (lookupResult?.status !== "confirmed" || !lookupResult.symbol) {
      setLookupPrice(null);
      return;
    }
    void api
      .stockQuotes(lookupResult.symbol)
      .then((quotes) => setLookupPrice(quotes[0]?.price ?? null))
      .catch(() => setLookupPrice(null));
  }, [lookupResult]);

  useEffect(() => {
    const fnMap: Partial<Record<string, Tab>> = {
      F1: "portfolio",
      F2: "risk",
      F3: "market",
      F4: "news",
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const next = fnMap[e.key];
      if (!next) return;
      e.preventDefault();
      setTab(next);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (tab !== "portfolio") return;
    void loadHoldings();
    const id = setInterval(() => void loadHoldings(), 30_000);
    return () => clearInterval(id);
  }, [tab]);

  const showError = useCallback((msg: string) => {
    setError(msg);
    setTimeout(() => setError(""), 4000);
  }, []);

  async function loadHoldings() {
    try {
      setHoldingsLoading(true);
      const data = await api.holdingsEnriched();
      setHoldings(data);
      refreshDataStatus();
      if (data.length === 0 && !autoDemoLoadRequested.current) {
        autoDemoLoadRequested.current = true;
        try {
          await api.loadDemo();
          setHoldings(await api.holdingsEnriched());
          setIsDemo(true);
        } catch {
          // ignore auto-load failures
        }
      }
    } catch (e) {
      showError(String(e));
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
    const requestQuery = activeContext
      ? `${query}\n\n[当前画布上下文：${activeContext.label}${activeContext.detail ? `；${activeContext.detail}` : ""}]`
      : query;
    try {
      const resp = await api.chatStream(
        requestQuery,
        sessionId,
        (event: AgentStreamEvent) => {
          if (
            event.type === "analysis_choice" ||
            event.type === "stock_choice" ||
            event.type === "route_choice"
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
        options,
      );
      if (resp) {
        setSessionId(resp.session_id);
        processSnapshot = {
          ...processSnapshot,
          streamStatus: processSnapshot.streamStatus || statusMsg || t("chat.analysisDone"),
        };
        const hasResearchCard = resp.cards?.some((c) => c.type === "research");
        const hasProcessTrail =
          processSnapshot.streamLog.length > 0 ||
          processSnapshot.agentSteps.length > 0 ||
          processSnapshot.debateRounds.length > 0 ||
          processSnapshot.judgeVerdict != null;
        const assistantMsg: Message = {
          role: "assistant",
          content: stripDisclaimer(resp.reply),
          cards: resp.cards,
          intent: resp.intent,
          followUpQuestions: resp.follow_up_questions ?? [],
          llmUsage: resp.llm_usage ?? null,
          process:
            hasProcessTrail || hasResearchCard
              ? processSnapshot
              : undefined,
        };
        setMessages((m) => [...m, assistantMsg]);
      }
    } catch {
      try {
        setStatusMsg(t("chat.streamFailed"));
        const resp = await api.chat(requestQuery, sessionId, options);
        setSessionId(resp.session_id);
        setMessages((m) => [
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
      } catch (e) {
        setMessages((m) => [...m, { role: "assistant", content: `Error: ${String(e)}` }]);
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
    setMessages((m) => [...m, { role: "user", content: query }]);
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

  function onTickerIndexClick(_name: string) {
    setTab("market");
    setPageContext({ kind: "market", label: _name });
    setCopilotOpen(true);
    setInput(t("chat.exampleMarketQuery"));
  }

  function askCopilot(query: string, context: CopilotContext) {
    setPageContext(context);
    setCopilotOpen(true);
    startChatQuery(query, { context });
  }

  function newCopilotThread() {
    setMessages([]);
    setSessionId(undefined);
    setChatStream(emptyStreamState());
    setStatusMsg("");
    setInput("");
  }

  function handleActionNavigate(target: string) {
    if (target === "risk") setTab("risk");
    else if (target === "news") setTab("news");
    else {
      setCopilotOpen(true);
    }
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
    setMessages((m) => [...m, { role: "user", content: `${name}（${symbol}）` }]);
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
    setMessages((m) => [
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

  async function lookupAndAdd() {
    if (!holdingInput.trim()) return;
    setLookupLoading(true);
    setLookupResult(null);
    try {
      const result = await api.lookupStock(holdingInput.trim());
      setLookupResult(result);
      if (result.status === "confirmed" && result.symbol && result.name) {
        const cost = holdingCost ? parseFloat(holdingCost) : 0;
        const lots = holdingLots ? parseInt(holdingLots) : 1;
        if (cost <= 0) {
          showError(t("portfolio.invalidCost"));
          return;
        }
        await api.addHolding({
          symbol: result.symbol,
          name: result.name,
          cost_price: cost,
          lots,
          sector: result.sector || undefined,
          buy_date: holdingDate || undefined,
        });
        await loadHoldings();
        setHoldingInput("");
        setHoldingCost("");
        setHoldingLots("");
        setHoldingDate("");
        setLookupResult(null);
      }
    } catch (e) {
      showError(String(e));
    } finally {
      setLookupLoading(false);
    }
  }

  async function confirmCandidate(symbol: string, name: string) {
    const cost = holdingCost ? parseFloat(holdingCost) : 0;
    const lots = holdingLots ? parseInt(holdingLots) : 1;
    if (cost <= 0) {
      showError(t("portfolio.invalidCost"));
      return;
    }
    try {
      await api.addHolding({ symbol, name, cost_price: cost, lots, buy_date: holdingDate || undefined });
      await loadHoldings();
      setHoldingInput("");
      setHoldingCost("");
      setHoldingLots("");
      setHoldingDate("");
      setLookupResult(null);
    } catch (e) {
      showError(String(e));
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
    <div className="app-shell">
      <div className="app-chrome">
        <div className="chrome-left">
          <span className="bbg-logo">StockResearch</span>
          <span className="chrome-sep">·</span>
          <ModeSwitcher settings={modeSettings} onSwitch={handleSwitchMode} />
        </div>
        <p className="chrome-disclaimer">{t("chat.disclaimer")}</p>
        <div className="chrome-meta">
          <button
            type="button"
            className={`data-source-badge${
              dataStatus && (dataStatus.quotes?.degraded || dataStatus.overview?.degraded) ? " degraded" : ""
            }`}
            title={dataStatus?.overview?.message || dataStatus?.quotes?.message || dataSourceLabel()}
            onClick={() => setDataDetailsOpen(true)}
          >
            {dataSourceLabel()}
          </button>
          {headerUsage && (
            <span className="chrome-usage" title={formatLlmUsage(headerUsage, t)}>
              {formatHeaderUsage(headerUsage, t)}
            </span>
          )}
          <span className="terminal-clock">{clock}</span>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setSetupOpen(true)}
          >
            {t("header.settings")}
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={toggleLocale}
          >
            {locale === "zh" ? "EN" : "中"}
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
      <CanvasNav
        tab={tab}
        items={navItems}
        copilotOpen={copilotOpen}
        copilotLabel={t("nav.copilot")}
        onTab={setTab}
        onCopilot={() => setCopilotOpen((open) => !open)}
      />
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

      <div className={`app-body canvas-shell${copilotOpen ? " copilot-open" : ""}${settingsRequired ? " app-locked" : ""}`}>
        <div className="main">
          {error && <div className="error">{error}</div>}
          {holdings.length === 0 && !isDemo && (
            <DemoBanner onLoad={loadDemoHoldings} onClear={clearDemoHoldings} isDemo={isDemo} loading={demoLoading} />
          )}
          {isDemo && (
            <DemoBanner
              onLoad={loadDemoHoldings}
              onClear={clearDemoHoldings}
              onGoPortfolio={() => setTab("portfolio")}
              isDemo={isDemo}
              loading={demoLoading}
            />
          )}

          {tab === "news" && (
            <NewsPanel
              news={news}
              newsLoading={newsLoading}
              newsSectors={newsSectors}
              sectorSaving={sectorSaving}
              onLoadNews={() => void loadNews()}
              onToggleSector={(s) => void toggleNewsSector(s)}
            />
          )}

          {tab === "portfolio" && (
            <>
              <ActionCenter onNavigate={handleActionNavigate} onChatQuery={(query) => {
                const context: CopilotContext = {
                  kind: "portfolio",
                  label: locale === "zh" ? "我的持仓" : "My holdings",
                };
                setPageContext(context);
                setCopilotOpen(true);
                startChatQuery(query, { context });
              }} />
              <PortfolioPanel
                holdings={holdings}
                holdingsLoading={holdingsLoading}
                portfolioSummary={portfolioSummary}
                sectorMix={sectorMix}
                numLocale={numLocale}
                holdingInput={holdingInput}
                holdingCost={holdingCost}
                holdingLots={holdingLots}
                holdingDate={holdingDate}
                lookupResult={lookupResult}
                lookupPrice={lookupPrice}
                lookupLoading={lookupLoading}
                onHoldingInputChange={setHoldingInput}
                onHoldingCostChange={setHoldingCost}
                onHoldingLotsChange={setHoldingLots}
                onHoldingDateChange={setHoldingDate}
                onClearLookup={() => setLookupResult(null)}
                onLoadHoldings={() => void loadHoldings()}
                onLookupAndAdd={() => void lookupAndAdd()}
                onConfirmCandidate={(symbol, name) => void confirmCandidate(symbol, name)}
                onDeleteHolding={(id) => void deleteHolding(id)}
                onAnalyzeHolding={analyzeHolding}
              />
            </>
          )}

          {tab === "risk" && (
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
                onGoPortfolio={() => setTab("portfolio")}
              />
            </>
          )}

          {tab === "market" && (
            <MarketPanel
              overview={marketOverview}
              loading={overviewLoading}
              onRefresh={() => void loadOverview()}
              onAskCopilot={(query) =>
                askCopilot(query, {
                  kind: "market",
                  label: locale === "zh" ? "当前市场" : "Current market",
                  detail: marketOverview?.data_status,
                })
              }
            />
          )}
        </div>

        <CopilotPanel
          open={copilotOpen}
          threadTitle={messages.find((message) => message.role === "user")?.content || ""}
          userContext={t("chat.holdingsContext", {
            n: String(holdings.length),
            mode: t(`mode.${modeSettings.mode}`),
          })}
          pageContext={pageContext}
          onClose={() => setCopilotOpen(false)}
          onNewThread={newCopilotThread}
          onRemoveContext={() => setPageContext(null)}
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
            enableGlossary={modeSettings.mode === "advisor" && modeSettings.enableGlossary}
            appMode={modeSettings.mode}
            glossary={glossary}
            onStartQuery={(query) => startChatQuery(query)}
            onSend={sendChat}
            onAnalyzeHolding={analyzeHolding}
            onConfirmStock={confirmChatStock}
            onConfirmRoute={confirmChatRoute}
          />
        </CopilotPanel>
      </div>
    </div>
  );
}
