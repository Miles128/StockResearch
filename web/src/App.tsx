import { useEffect, useMemo, useState } from "react";
import {
  api,
  AgentStreamEvent,
  ChatStreamOptions,
  DataSourceStatus,
  HoldingEnriched,
  LlmUsage,
  MarketOverview,
  NewsItem,
  RiskCheckup,
  SectorPreferences,
  StockLookupOut,
} from "./api";
import type { Message, Tab } from "./appTypes";
import { ChatPanel } from "./ChatPanel";
import { useI18n } from "./i18n";
import { isLlmConfigured } from "./llmSettings";
import { formatHeaderUsage, formatLlmUsage } from "./llmUsageFormat";
import { MarketTicker } from "./MarketTicker";
import { NewsPanel } from "./NewsPanel";
import { computePortfolioSummary, computeSectorConcentration } from "./portfolioHelpers";
import { PortfolioPanel } from "./PortfolioPanel";
import { RiskPanel } from "./RiskPanel";
import { SettingsPanel } from "./SettingsPanel";
import { stripDisclaimer } from "./disclaimerText";
import { applyStreamEvent, emptyStreamState } from "./streamEvents";
import { TabNav } from "./TabNav";

export default function App() {
  const { t, locale, setLocale } = useI18n();
  const navItems = useMemo(
    () => [
      { key: "chat" as Tab, label: t("nav.chat"), fn: "F1" },
      { key: "news" as Tab, label: t("nav.news"), fn: "F2" },
      { key: "portfolio" as Tab, label: t("nav.portfolio"), fn: "F3" },
      { key: "risk" as Tab, label: t("nav.risk"), fn: "F4" },
      { key: "settings" as Tab, label: t("nav.settings"), fn: "F5" },
    ],
    [t, locale],
  );
  const pageTitles: Record<Tab, string> = {
    chat: t("page.chat"),
    news: t("page.news"),
    portfolio: t("page.portfolio"),
    risk: t("page.risk"),
    settings: t("page.settings"),
  };
  const numLocale = locale === "zh" ? "zh-CN" : "en-US";
  const ratioGrade = (v: number, excellent: number, good: number) =>
    v > excellent ? t("rating.excellent") : v > good ? t("rating.good") : v > 0 ? t("rating.fair") : t("rating.poor");

  const [tab, setTab] = useState<Tab>("chat");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [loading, setLoading] = useState(false);
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
  const [llmConfigured, setLlmConfigured] = useState(isLlmConfigured);
  const [setupOpen, setSetupOpen] = useState(!isLlmConfigured());
  const [dataStatus, setDataStatus] = useState<DataSourceStatus | null>(null);
  const [marketOverview, setMarketOverview] = useState<MarketOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [lookupPrice, setLookupPrice] = useState<number | null>(null);
  const [newsSectors, setNewsSectors] = useState<SectorPreferences | null>(null);
  const [sectorSaving, setSectorSaving] = useState(false);
  const settingsRequired = !llmConfigured;

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
    void loadOverview();
    void loadHoldings();
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
      F1: "chat",
      F2: "news",
      F3: "portfolio",
      F4: "risk",
      F5: "settings",
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

  function showError(msg: string) {
    setError(msg);
    setTimeout(() => setError(""), 4000);
  }

  async function loadHoldings() {
    try {
      setHoldingsLoading(true);
      setHoldings(await api.holdingsEnriched());
      refreshDataStatus();
    } catch (e) {
      showError(String(e));
    } finally {
      setHoldingsLoading(false);
    }
  }

  async function executeChat(query: string, options?: ChatStreamOptions) {
    setLoading(true);
    setStatusMsg(t("chat.connecting"));
    setChatStream(emptyStreamState());
    let processSnapshot = emptyStreamState();
    try {
      const resp = await api.chatStream(
        query,
        sessionId,
        (event: AgentStreamEvent) => {
          if (event.type === "analysis_choice" || event.type === "stock_choice") return;
          setChatStream((prev) => {
            const next = applyStreamEvent(prev, event);
            processSnapshot = next;
            return next;
          });
          if (event.type === "status" && event.message) {
            setStatusMsg(event.message);
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
        const assistantMsg: Message = {
          role: "assistant",
          content: stripDisclaimer(resp.reply),
          cards: resp.cards,
          intent: resp.intent,
          llmUsage: resp.llm_usage ?? null,
          process:
            processSnapshot.streamLog.length > 0 ||
            processSnapshot.agentSteps.length > 0 ||
            processSnapshot.debateRounds.length > 0 ||
            processSnapshot.judgeVerdict
              ? processSnapshot
              : undefined,
        };
        setMessages((m) => [...m, assistantMsg]);
      }
    } catch {
      try {
        setStatusMsg(t("chat.streamFailed"));
        const resp = await api.chat(query, sessionId, options);
        setSessionId(resp.session_id);
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: stripDisclaimer(resp.reply),
            cards: resp.cards,
            intent: resp.intent,
            llmUsage: resp.llm_usage ?? null,
          },
        ]);
      } catch (e) {
        setMessages((m) => [...m, { role: "assistant", content: `Error: ${String(e)}` }]);
      }
    } finally {
      setLoading(false);
      setStatusMsg("");
    }
  }

  function startChatQuery(query: string, opts?: { switchTab?: boolean }) {
    if (!query.trim() || loading) return;
    if (opts?.switchTab) setTab("chat");
    setInput("");
    setMessages((m) => [...m, { role: "user", content: query }]);
    void executeChat(query);
  }

  function sendChat() {
    if (!input.trim() || loading) return;
    startChatQuery(input.trim());
  }

  function analyzeHolding(h: HoldingEnriched) {
    const q = locale === "zh" ? `分析${h.name}` : `Analyze ${h.name}`;
    startChatQuery(q, { switchTab: true });
  }

  function onTickerIndexClick(_name: string) {
    setTab("chat");
    setInput(t("chat.exampleMarketQuery"));
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
    if (loading) return;
    setMessages((m) => [...m, { role: "user", content: `${name}（${symbol}）` }]);
    void executeChat(originalMessage, { confirmedSymbol: symbol, confirmedName: name });
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
      setLoading(true);
      setRisk(await api.riskCheckup());
    } catch (e) {
      showError(String(e));
    } finally {
      setLoading(false);
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
      <TabNav
        className="tab-nav-mobile"
        compact
        tab={tab}
        onTab={setTab}
        items={navItems}
        ariaLabel={t("nav.aria")}
        locale={locale}
        onLocaleToggle={toggleLocale}
      />
      <div className="app-chrome">
        <div className="chrome-left">
          <span className="bbg-logo">StockResearch</span>
          <span className="chrome-sep">·</span>
          <span className="chrome-page-title">{pageTitles[tab]}</span>
        </div>
        <p className="chrome-disclaimer">{t("chat.disclaimer")}</p>
        <div className="chrome-meta">
          <span
            className={`data-source-badge${
              dataStatus && (dataStatus.quotes?.degraded || dataStatus.overview?.degraded) ? " degraded" : ""
            }`}
            title={dataStatus?.overview?.message || dataStatus?.quotes?.message || dataSourceLabel()}
          >
            {dataSourceLabel()}
          </span>
          {headerUsage && (
            <span className="chrome-usage" title={formatLlmUsage(headerUsage, t)}>
              {formatHeaderUsage(headerUsage, t)}
            </span>
          )}
          <span className="terminal-clock">{clock}</span>
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
      <SettingsPanel
        open={setupOpen}
        onClose={() => setSetupOpen(false)}
        required={settingsRequired}
        onConfigured={handleLlmConfigured}
        variant="modal"
      />

      <div className={`app-body${settingsRequired ? " app-locked" : ""}`}>
        <aside className="sidebar">
          <TabNav
            className="tab-nav-desktop"
            tab={tab}
            onTab={setTab}
            items={navItems}
            ariaLabel={t("nav.aria")}
            locale={locale}
            onLocaleToggle={toggleLocale}
          />
        </aside>

        <div className="main">
          {error && <div className="error">{error}</div>}

          {tab === "chat" && (
            <ChatPanel
              messages={messages}
              loading={loading}
              statusMsg={statusMsg}
              chatStream={chatStream}
              input={input}
              onInputChange={setInput}
              chatExamples={chatExamples}
              holdings={holdings}
              onStartQuery={(q) => startChatQuery(q)}
              onSend={sendChat}
              onAnalyzeHolding={analyzeHolding}
              onConfirmStock={confirmChatStock}
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
          )}

          {tab === "risk" && (
            <RiskPanel
              holdings={holdings}
              risk={risk}
              loading={loading}
              numLocale={numLocale}
              ratioGrade={ratioGrade}
              alertHoldingTags={alertHoldingTags}
              onRunRisk={() => void runRisk()}
              onGoPortfolio={() => setTab("portfolio")}
            />
          )}

          {tab === "settings" && (
            <div className="panel settings-page-panel">
              <SettingsPanel open variant="inline" onClose={() => setTab("chat")} onConfigured={handleLlmConfigured} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
