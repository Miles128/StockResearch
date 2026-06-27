import { Component, useCallback, useEffect, useMemo, useRef, useState, type ErrorInfo, type ReactNode } from "react";
import {
  api,
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
import type { CopilotContext, Tab } from "./appTypes";
import { BackendHealthBanner } from "./BackendHealthBanner";
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
import { ModeSwitcher } from "./ModeSwitcher";
import { Onboarding } from "./Onboarding";
import { AssetAllocationPanel } from "./AssetAllocationPanel";
import { useCopilotChat } from "./hooks/useCopilotChat";
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
  const chat = useCopilotChat({
    pageContext,
    onOpenCopilot: () => setCopilotOpen(true),
    onSetPageContext: setPageContext,
    locale,
  });
  const [riskLoading, setRiskLoading] = useState(false);
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
    for (let i = chat.messages.length - 1; i >= 0; i -= 1) {
      const m = chat.messages[i];
      if (m.role === "assistant" && m.llmUsage && m.llmUsage.total_tokens > 0) {
        return m.llmUsage;
      }
    }
    return null;
  }, [chat.messages]);

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

  function onTickerIndexClick(_name: string) {
    setTab("market");
    setPageContext({ kind: "market", label: _name });
    setCopilotOpen(true);
    chat.setInput(t("chat.exampleMarketQuery"));
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
      <BackendHealthBanner />
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
                chat.startChatQuery(query, {
                  context: {
                    kind: "portfolio",
                    label: locale === "zh" ? "我的持仓" : "My holdings",
                  },
                });
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
                onAnalyzeHolding={chat.analyzeHolding}
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
                chat.askCopilot(query, {
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
          threadTitle={chat.messages.find((message) => message.role === "user")?.content || ""}
          userContext={t("chat.holdingsContext", {
            n: String(holdings.length),
            mode: t(`mode.${modeSettings.mode}`),
          })}
          pageContext={pageContext}
          onClose={() => setCopilotOpen(false)}
          onNewThread={chat.newCopilotThread}
          onRemoveContext={() => setPageContext(null)}
        >
          <ChatPanel
            messages={chat.messages}
            loading={chat.chatLoading}
            statusMsg={chat.statusMsg}
            chatStream={chat.chatStream}
            input={chat.input}
            onInputChange={chat.setInput}
            chatExamples={chatExamples}
            holdings={holdings}
            enableGlossary={modeSettings.mode === "advisor" && modeSettings.enableGlossary}
            appMode={modeSettings.mode}
            glossary={glossary}
            onStartQuery={(query) => chat.startChatQuery(query)}
            onSend={chat.sendChat}
            onAnalyzeHolding={chat.analyzeHolding}
            onConfirmStock={chat.confirmChatStock}
            onConfirmRoute={chat.confirmChatRoute}
          />
        </CopilotPanel>
      </div>
    </div>
  );
}
