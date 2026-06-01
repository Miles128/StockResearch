import { useCallback, useEffect, useState } from "react";
import {
  api,
  ChatResponse,
  Holding,
  MarketOverview,
  NewsItem,
  ResearchReport,
  RiskCheckup,
  StockQuote,
} from "./api";
import { MarkdownContent } from "./MarkdownContent";
import { StreamFeed } from "./StreamFeed";
import { applyStreamEvent, emptyStreamState } from "./streamEvents";

type Tab = "chat" | "market" | "news" | "portfolio" | "research" | "risk";

interface Message {
  role: "user" | "assistant";
  content: string;
  cards?: ChatResponse["cards"];
}

const TABS: { id: Tab; label: string }[] = [
  { id: "chat", label: "AI 对话" },
  { id: "market", label: "市场行情" },
  { id: "news", label: "快讯" },
  { id: "portfolio", label: "持仓" },
  { id: "research", label: "投研" },
  { id: "risk", label: "风控" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [availableSectors, setAvailableSectors] = useState<string[]>([]);
  const [selectedSectors, setSelectedSectors] = useState<string[]>([]);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [risk, setRisk] = useState<RiskCheckup | null>(null);
  const [market, setMarket] = useState<MarketOverview | null>(null);
  const [quotes, setQuotes] = useState<StockQuote[]>([]);
  const [error, setError] = useState("");
  const [stockQuery, setStockQuery] = useState("");
  const [costPrice, setCostPrice] = useState(0);
  const [lots, setLots] = useState(1);
  const [addingHolding, setAddingHolding] = useState(false);
  const [loadingQuote, setLoadingQuote] = useState(false);
  const [backfillingSectors, setBackfillingSectors] = useState(false);
  const [researchQuery, setResearchQuery] = useState("");
  const [researchTarget, setResearchTarget] = useState<{ symbol: string; name: string } | null>(null);
  const [researchReport, setResearchReport] = useState<ResearchReport | null>(null);
  const [loadingResearch, setLoadingResearch] = useState(false);
  const [lookingUpResearch, setLookingUpResearch] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [loadingNews, setLoadingNews] = useState(false);
  const [newsProgress, setNewsProgress] = useState<{ pct: number; label: string } | null>(null);
  const [refreshingMarket, setRefreshingMarket] = useState(false);
  const [savingSector, setSavingSector] = useState(false);
  const [loadingRisk, setLoadingRisk] = useState(false);
  const [chatStream, setChatStream] = useState(emptyStreamState());
  const [researchStream, setResearchStream] = useState(emptyStreamState());
  const [riskStream, setRiskStream] = useState(emptyStreamState());
  const [chatDraftReply, setChatDraftReply] = useState("");
  const [pendingAdd, setPendingAdd] = useState<{
    status: "ambiguous" | "confirmed";
    message: string;
    symbol?: string;
    name?: string;
    marketPrice?: number | null;
    changePct?: number | null;
    sector?: string | null;
    candidates: { symbol: string; name: string }[];
  } | null>(null);
  const [successMsg, setSuccessMsg] = useState("");

  const showError = useCallback((msg: string) => {
    setError(msg);
    setTimeout(() => setError(""), 6000);
  }, []);

  const showSuccess = useCallback((msg: string) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(""), 4000);
  }, []);

  const loadOverview = useCallback(async () => {
    try {
      setError("");
      const overview = await api.marketOverview();
      setMarket(overview);
    } catch (e) {
      showError(String(e));
    }
  }, [showError]);

  const loadQuotes = useCallback(async (symbols?: string) => {
    const stockQuotes = await api.stockQuotes(symbols);
    setQuotes(stockQuotes);
  }, []);

  const refreshMarket = useCallback(async () => {
    if (refreshingMarket) return;
    setRefreshingMarket(true);
    try {
      setError("");
      const overview = await api.marketOverview();
      setMarket(overview);
      const symbols =
        holdings.length > 0
          ? [...new Set(holdings.map((h) => h.symbol))].join(",")
          : undefined;
      try {
        await loadQuotes(symbols);
      } catch (e) {
        showError(`指数已更新，个股行情失败：${String(e)}`);
      }
      const sh = overview.indices.find((i) => i.name === "上证指数");
      if (overview.data_status === "unavailable") {
        showError(overview.message || "行情源暂时不可用");
      } else {
        showSuccess(
          sh
            ? `行情已刷新 · 上证 ${sh.price.toFixed(2)} (${sh.change_pct >= 0 ? "+" : ""}${sh.change_pct.toFixed(2)}%)`
            : "行情已刷新",
        );
      }
    } catch (e) {
      showError(String(e));
    } finally {
      setRefreshingMarket(false);
    }
  }, [refreshingMarket, holdings, loadQuotes, showError, showSuccess]);

  const loadHoldings = useCallback(async () => {
    try {
      const list = await api.holdings();
      setHoldings(list);
    } catch (e) {
      showError(String(e));
    }
  }, [showError]);

  useEffect(() => {
    void loadHoldings();
    void loadOverview();
  }, [loadHoldings, loadOverview]);

  useEffect(() => {
    if (tab === "market" || tab === "portfolio") {
      const symbols =
        tab === "portfolio" && holdings.length > 0
          ? [...new Set(holdings.map((h) => h.symbol))].join(",")
          : undefined;
      void loadQuotes(symbols).catch(() => {
        // 初次进入 tab 时行情失败不弹窗，点「刷新行情」会有明确反馈
      });
    }
  }, [tab, holdings, loadQuotes]);

  useEffect(() => {
    const timer = setInterval(loadOverview, 60000);
    return () => clearInterval(timer);
  }, [loadOverview]);

  useEffect(() => {
    if (tab === "news") {
      void loadSectorPrefs();
      void refreshNewsFeed();
    }
  }, [tab]);

  useEffect(() => {
    if (tab === "portfolio") loadHoldings();
  }, [tab, loadHoldings]);

  async function refreshNewsFeed() {
    try {
      setNews(await api.newsFeed());
    } catch (e) {
      showError(String(e));
    }
  }

  async function loadSectorPrefs() {
    try {
      const prefs = await api.sectorPrefs();
      setAvailableSectors(prefs.available);
      setSelectedSectors(prefs.selected);
    } catch (e) {
      showError(String(e));
    }
  }

  async function toggleSector(sector: string) {
    if (savingSector || loadingNews) return;
    const next = selectedSectors.includes(sector)
      ? selectedSectors.filter((s) => s !== sector)
      : [...selectedSectors, sector];
    setSavingSector(true);
    try {
      const prefs = await api.updateSectorPrefs(next);
      setSelectedSectors(prefs.selected);
      await refreshNewsFeed();
      showSuccess(`板块偏好已更新${prefs.selected.length ? `：${prefs.selected.join("、")}` : ""}`);
    } catch (e) {
      showError(String(e));
    } finally {
      setSavingSector(false);
    }
  }

  async function sendChat() {
    if (!input.trim() || loading) return;
    setLoading(true);
    const userMsg = input;
    setInput("");
    setChatDraftReply("");
    setChatStream(emptyStreamState());
    setMessages((m) => [...m, { role: "user", content: userMsg }]);
    let draftReply = "";
    try {
      const done = await api.chatStream(userMsg, sessionId, (event) => {
        setChatStream((s) => applyStreamEvent(s, event));
        if (event.type === "reply" && event.content) {
          draftReply = event.content;
          setChatDraftReply(event.content);
        }
      });
      const resp = done?.response;
      if (resp) {
        setSessionId(resp.session_id);
        setMessages((m) => [
          ...m,
          { role: "assistant", content: resp.reply, cards: resp.cards },
        ]);
      } else if (draftReply) {
        setMessages((m) => [...m, { role: "assistant", content: draftReply }]);
      }
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: `❌ ${String(e)}` }]);
    } finally {
      setLoading(false);
      setChatStream(emptyStreamState());
      setChatDraftReply("");
    }
  }

  async function ingestNews() {
    if (loadingNews) return;
    setLoadingNews(true);
    setNewsProgress({ pct: 8, label: "正在拉取持仓、板块与大盘快讯…" });
    const timer = window.setInterval(() => {
      setNewsProgress((prev) => {
        if (!prev || prev.pct >= 88) return prev;
        return { ...prev, pct: prev.pct + 4 };
      });
    }, 500);
    try {
      const result = await api.ingestNews();
      setNewsProgress({
        pct: 92,
        label: `${result.message}（扫描 ${result.scanned} 条，跳过 ${result.skipped} 条无关${result.purged ? `，清理 ${result.purged} 条旧快讯` : ""}）`,
      });
      setNews(await api.newsFeed());
      setNewsProgress({ pct: 100, label: "快讯已更新" });
    } catch (e) {
      showError(String(e));
      setNewsProgress(null);
    } finally {
      window.clearInterval(timer);
      setLoadingNews(false);
      window.setTimeout(() => setNewsProgress(null), 1200);
    }
  }

  async function runRisk() {
    if (loadingRisk) return;
    setLoadingRisk(true);
    setRisk(null);
    setRiskStream(emptyStreamState());
    try {
      const result = await api.riskCheckupStream((event) => {
        setRiskStream((s) => applyStreamEvent(s, event));
      });
      if (result) setRisk(result);
      showSuccess("多 Agent 风控会诊完成");
    } catch (e) {
      showError(String(e));
    } finally {
      setLoadingRisk(false);
    }
  }

  async function removeHolding(id: number) {
    setDeletingId(id);
    try {
      await api.deleteHolding(id);
      setHoldings((prev) => prev.filter((h) => h.id !== id));
    } catch (e) {
      showError(String(e));
    } finally {
      setDeletingId(null);
    }
  }

  async function presentPendingStock(
    symbol: string,
    name: string,
    message: string,
    sectorHint?: string | null,
  ) {
    setLoadingQuote(true);
    try {
      const rows = await api.stockQuotes(symbol);
      const quote = rows[0];
      const marketPrice = quote?.price ?? null;
      const sector = quote?.sector ?? sectorHint ?? null;
      if (marketPrice && marketPrice > 0) {
        setCostPrice(Number(marketPrice.toFixed(2)));
      }
      setPendingAdd({
        status: "confirmed",
        message,
        symbol,
        name,
        marketPrice,
        changePct: quote?.change_pct ?? null,
        sector,
        candidates: [],
      });
    } catch {
      setPendingAdd({
        status: "confirmed",
        message,
        symbol,
        name,
        marketPrice: null,
        changePct: null,
        sector: sectorHint ?? null,
        candidates: [],
      });
      showError("现价获取失败，请手动填写成本价");
    } finally {
      setLoadingQuote(false);
    }
  }

  async function saveHolding(symbol: string, name: string, sector?: string | null) {
    const saved = await api.confirmHolding({
      symbol,
      name,
      cost_price: costPrice,
      lots,
      sector: sector && sector !== "未知" ? sector : undefined,
    });
    setPendingAdd(null);
    setStockQuery("");
    await loadHoldings();
    const totalLots = Math.round(saved.quantity / 100);
    showSuccess(`已保存 ${saved.name}（${saved.symbol}），共 ${totalLots} 手`);
  }

  async function confirmAddHolding() {
    if (!pendingAdd?.symbol || !pendingAdd.name || addingHolding) return;
    if (costPrice <= 0) {
      showError("成本价必须大于 0");
      return;
    }
    if (lots <= 0 || !Number.isInteger(lots)) {
      showError("持仓手数必须是大于 0 的整数");
      return;
    }
    setAddingHolding(true);
    try {
      await saveHolding(pendingAdd.symbol, pendingAdd.name, pendingAdd.sector);
    } catch (e) {
      showError(String(e));
    } finally {
      setAddingHolding(false);
    }
  }

  async function selectCandidate(symbol: string, name: string) {
    if (addingHolding || loadingQuote) return;
    setAddingHolding(true);
    try {
      await presentPendingStock(symbol, name, `已识别：${name}（${symbol}）`);
    } finally {
      setAddingHolding(false);
    }
  }

  async function lookupStockForAdd() {
    const query = stockQuery.trim();
    if (!query) {
      showError("请输入股票代码或名称");
      return;
    }
    setAddingHolding(true);
    setPendingAdd(null);
    setCostPrice(0);
    try {
      const lookup = await api.lookupStock(query);
      if (lookup.status === "not_found") {
        showError(lookup.message);
        return;
      }
      if (lookup.status === "confirmed" && lookup.symbol && lookup.name) {
        await presentPendingStock(
          lookup.symbol,
          lookup.name,
          lookup.message,
          lookup.sector,
        );
        return;
      }
      if (lookup.candidates.length > 0) {
        setPendingAdd({
          status: "ambiguous",
          message: lookup.message,
          candidates: lookup.candidates,
        });
        return;
      }
      showError(lookup.message);
    } catch (e) {
      showError(String(e));
    } finally {
      setAddingHolding(false);
    }
  }

  async function lookupResearchStock() {
    const query = researchQuery.trim();
    if (!query) {
      showError("请输入股票代码或名称");
      return;
    }
    setLookingUpResearch(true);
    setResearchReport(null);
    try {
      const lookup = await api.lookupStock(query);
      if (lookup.status === "not_found") {
        showError(lookup.message);
        return;
      }
      if (lookup.status === "confirmed" && lookup.symbol && lookup.name) {
        setResearchTarget({ symbol: lookup.symbol, name: lookup.name });
        return;
      }
      if (lookup.candidates.length === 1) {
        const c = lookup.candidates[0];
        setResearchTarget({ symbol: c.symbol, name: c.name });
        return;
      }
      if (lookup.candidates.length > 1) {
        showError(`${lookup.message} 请输入更精确的名称或 6 位代码`);
        return;
      }
      showError(lookup.message);
    } catch (e) {
      showError(String(e));
    } finally {
      setLookingUpResearch(false);
    }
  }

  async function runResearch(symbol: string, name: string) {
    if (loadingResearch) return;
    setResearchTarget({ symbol, name });
    setLoadingResearch(true);
    setResearchReport(null);
    setResearchStream(emptyStreamState());
    try {
      const done = await api.researchStream(symbol, (event) => {
        setResearchStream((s) => applyStreamEvent(s, event));
      });
      const report = done?.result as ResearchReport | undefined;
      if (report) {
        setResearchReport(report);
        showSuccess(`${report.name} 投研报告已生成`);
      }
    } catch (e) {
      showError(String(e));
    } finally {
      setLoadingResearch(false);
    }
  }

  async function backfillSectors() {
    if (backfillingSectors) return;
    setBackfillingSectors(true);
    try {
      const result = await api.backfillSectors();
      await loadHoldings();
      showSuccess(result.message);
    } catch (e) {
      showError(String(e));
    } finally {
      setBackfillingSectors(false);
    }
  }

  const holdingCount = new Set(holdings.map((h) => h.symbol)).size;
  const unknownSectorCount = holdings.filter((h) => !h.sector || h.sector === "未知").length;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">投小宝</div>
        <div className="brand-sub">Multi-Agent 投研</div>
        <div className="stat-pill" style={{ marginBottom: 16, width: "100%" }}>
          持仓 {holdingCount} 只
        </div>
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`nav-btn ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </aside>

      <main className="main">
        <div className="topbar">
          <div>
            <h2 style={{ margin: 0, fontSize: "1.35rem" }}>{TABS.find((t) => t.id === tab)?.label}</h2>
            <p className="muted" style={{ margin: "4px 0 0" }}>
              行情源：{market?.source ?? "加载中…"}
              {market?.data_status === "live" ? " · 实时" : market?.data_status === "mock" ? " · 演示数据" : ""}
            </p>
          </div>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => void refreshMarket()}
            disabled={refreshingMarket}
          >
            {refreshingMarket ? "刷新中…" : "刷新行情"}
          </button>
        </div>

        {market?.data_status === "mock" && (
          <div className="error">⚠️ 当前是写死的演示数据，不是真实行情。请设置 USE_MOCK_MARKET_DATA=false 并重启后端。</div>
        )}
        {market?.message && market.data_status !== "mock" && (
          <div className="stat-pill" style={{ marginBottom: 12 }}>{market.message}</div>
        )}

        {market && (
          <div className="ticker-strip">
            {market.indices.map((idx) => (
              <div className="ticker-card" key={idx.symbol}>
                <div className="ticker-name">{idx.name}</div>
                <div className="ticker-price">{idx.price.toFixed(2)}</div>
                <div className={`ticker-change ${idx.change_pct >= 0 ? "up" : "down"}`}>
                  {idx.change_pct >= 0 ? "+" : ""}{idx.change_pct.toFixed(2)}%
                </div>
              </div>
            ))}
          </div>
        )}

        {error && <div className="error">{error}</div>}
        {successMsg && <div className="success">{successMsg}</div>}

        {tab === "chat" && (
          <div className="panel">
            <div className="chat-messages">
              {messages.length === 0 && (
                <>
                  <p className="muted">试试：帮我分析一下贵州茅台 / 我的持仓风险大吗</p>
                  <p className="muted">投研卡片会出现在 AI 回复下方；也可打开左侧「投研」Tab 直接分析。</p>
                </>
              )}
              {messages.map((m, i) => (
                <div key={i}>
                  <div className={`message ${m.role}`}>
                    {m.role === "assistant" ? (
                      <MarkdownContent text={m.content} />
                    ) : (
                      m.content
                    )}
                  </div>
                  {m.cards?.map((c, j) => <CardView key={j} card={c} />)}
                </div>
              ))}
              {loading && (
                <div className="message assistant">
                  {chatDraftReply ? (
                    <MarkdownContent text={chatDraftReply} />
                  ) : (
                    <p className="muted">正在为您分析，请稍候…</p>
                  )}
                  <StreamFeed {...chatStream} />
                </div>
              )}
            </div>
            <div className="chat-input-row">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendChat()}
                placeholder="输入问题，自动路由新闻/投研/风控 Agent..."
              />
              <button type="button" className="btn btn-primary" onClick={sendChat} disabled={loading}>
                {loading ? "分析中" : "发送"}
              </button>
            </div>
            <p className="disclaimer" style={{ marginTop: 12 }}>
              以上内容由 AI 生成，仅供参考，不构成投资建议。
            </p>
          </div>
        )}

        {tab === "market" && (
          <div className="grid-2">
            <div className="panel">
              <h3 className="panel-title">大盘概览</h3>
              {market && (
                <div className="stat-row">
                  <span className="stat-pill">来源 {market.source}</span>
                  {market.northbound_net_yi != null && (
                    <span className="stat-pill">北向 {market.northbound_net_yi.toFixed(1)} 亿</span>
                  )}
                  {market.advancers != null && (
                    <span className="stat-pill up">上涨 {market.advancers}</span>
                  )}
                  {market.decliners != null && (
                    <span className="stat-pill down">下跌 {market.decliners}</span>
                  )}
                </div>
              )}
              <div className="quote-row" style={{ fontWeight: 600, color: "var(--muted)" }}>
                <span>名称</span><span>现价</span><span>涨跌幅</span><span>成交量</span>
              </div>
              {quotes.length === 0 ? (
                <p className="muted">暂无持仓，不展示样例股。录入持仓后可看个性化行情。</p>
              ) : (
                quotes.map((q) => (
                <div className="quote-row" key={q.symbol}>
                  <span>{q.name} ({q.symbol})</span>
                  <span>{q.price.toFixed(2)}</span>
                  <span className={q.change_pct >= 0 ? "up" : "down"}>
                    {q.change_pct >= 0 ? "+" : ""}{q.change_pct.toFixed(2)}%
                  </span>
                  <span className="muted">{(q.volume / 1e4).toFixed(0)} 万</span>
                </div>
              )))}
            </div>
            <div className="panel">
              <h3 className="panel-title">持仓实时行情</h3>
              {holdings.length === 0 ? (
                <p className="muted">录入持仓后此处显示个性化行情</p>
              ) : (
                holdings.map((h) => {
                  const q = quotes.find((x) => x.symbol === h.symbol);
                  const pnl = q ? ((q.price - h.cost_price) / h.cost_price) * 100 : 0;
                  return (
                    <div className="holding-row" key={h.id}>
                      <div>
                        <strong>{h.name}</strong>
                        <div className="muted">{h.symbol} · 成本 {h.cost_price}</div>
                      </div>
                      <div className={pnl >= 0 ? "up" : "down"}>
                        {q ? q.price.toFixed(2) : "--"} ({pnl >= 0 ? "+" : ""}{pnl.toFixed(1)}%)
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {tab === "news" && (
          <div className="panel">
            <h3 className="panel-title">关注板块</h3>
            <p className="muted" style={{ marginTop: 0 }}>
              快讯仅展示：市场要闻 + 你选的板块 + 持仓/自选股票相关
            </p>
            <div className="sector-grid">
              {availableSectors.map((sector) => (
                <button
                  key={sector}
                  type="button"
                  className={`sector-chip ${selectedSectors.includes(sector) ? "active" : ""}`}
                  disabled={savingSector || loadingNews}
                  onClick={() => void toggleSector(sector)}
                >
                  {sector}
                </button>
              ))}
            </div>
            <div style={{ marginTop: 20, marginBottom: 16 }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void ingestNews()}
                disabled={loadingNews || savingSector}
              >
                {loadingNews ? "抓取中…" : "抓取并刷新快讯"}
              </button>
            </div>
            {newsProgress && (
              <div className="progress-block">
                <div className="progress-label">{newsProgress.label}</div>
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${newsProgress.pct}%` }} />
                </div>
              </div>
            )}
            {news.length === 0 && !loadingNews && (
              <p className="muted">暂无快讯。请选择板块或添加持仓后点击抓取。</p>
            )}
            {(["market", "sector", "holding"] as const).map((group) => {
              const items = news.filter((n) => n.category === group);
              if (items.length === 0) return null;
              const title =
                group === "market" ? "市场快讯" : group === "sector" ? "板块快讯" : "持仓相关";
              return (
                <div key={group} style={{ marginTop: 20 }}>
                  <h4 className="panel-title">{title}</h4>
                  {items.map((n, i) => (
                    <div className="card" key={`${group}-${i}`}>
                      <h4>{n.title}</h4>
                      <MarkdownContent text={n.summary} />
                      <small className="muted">
                        {n.sentiment} · {n.impact_level}
                        {n.related_to_user ? " · 与你相关" : ""}
                      </small>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}

        {tab === "portfolio" && (
          <div className="panel">
            <h3 className="panel-title">添加持仓</h3>
            <p className="muted" style={{ marginTop: 0 }}>
              先识别股票，确认后会显示现价，再填写你的买入成本。
            </p>
            <div className="holding-form holding-form-lookup">
              <label className="field">
                <span className="field-label">股票代码或名称</span>
                <input
                  placeholder="如 600519、贵州茅台、茅台"
                  value={stockQuery}
                  onChange={(e) => setStockQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void lookupStockForAdd();
                  }}
                />
              </label>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void lookupStockForAdd()}
                disabled={addingHolding || loadingQuote}
              >
                {addingHolding ? "大模型识别中…" : "识别股票"}
              </button>
            </div>

            {pendingAdd && (
              <div className="confirm-card">
                <p>{pendingAdd.message}</p>
                {pendingAdd.status === "ambiguous" && (
                  <>
                    <div className="candidate-list">
                      {pendingAdd.candidates.map((c) => (
                        <button
                          key={c.symbol}
                          type="button"
                          className="btn btn-ghost"
                          disabled={addingHolding || loadingQuote}
                          onClick={() => void selectCandidate(c.symbol, c.name)}
                        >
                          是这只：{c.name}（{c.symbol}）
                        </button>
                      ))}
                    </div>
                    <button type="button" className="btn btn-ghost" onClick={() => setPendingAdd(null)}>
                      取消
                    </button>
                  </>
                )}
                {pendingAdd.status === "confirmed" && pendingAdd.symbol && pendingAdd.name && (
                  <>
                    <div className="market-price-row">
                      <span className="field-label">行业</span>
                      <span>{pendingAdd.sector && pendingAdd.sector !== "未知" ? pendingAdd.sector : "识别中…"}</span>
                    </div>
                    <div className="market-price-row">
                      <span className="field-label">现价</span>
                      {loadingQuote ? (
                        <span className="muted">获取行情中…</span>
                      ) : pendingAdd.marketPrice != null ? (
                        <span>
                          <strong>{pendingAdd.marketPrice.toFixed(2)}</strong> 元/股
                          {pendingAdd.changePct != null && (
                            <span className={pendingAdd.changePct >= 0 ? "up" : "down"}>
                              {" "}
                              {pendingAdd.changePct >= 0 ? "+" : ""}
                              {pendingAdd.changePct.toFixed(2)}%
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="muted">暂无行情，请手动填写成本价</span>
                      )}
                    </div>
                    <div className="holding-form holding-form-confirm">
                      <label className="field">
                        <span className="field-label">成本价（元/股）</span>
                        <input
                          type="number"
                          min={0.01}
                          step={0.01}
                          placeholder="你的买入价，可参考现价"
                          value={costPrice > 0 ? costPrice : ""}
                          onChange={(e) =>
                            setCostPrice(e.target.value === "" ? 0 : Number(e.target.value))
                          }
                        />
                      </label>
                      <label className="field">
                        <span className="field-label">持仓手数</span>
                        <input
                          type="number"
                          min={1}
                          step={1}
                          placeholder="几手"
                          value={lots}
                          onChange={(e) => setLots(Number(e.target.value))}
                        />
                      </label>
                    </div>
                    <div className="confirm-actions">
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => void confirmAddHolding()}
                        disabled={addingHolding || loadingQuote}
                      >
                        {addingHolding ? "保存中…" : "确认添加"}
                      </button>
                      <button type="button" className="btn btn-ghost" onClick={() => setPendingAdd(null)}>
                        取消
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {holdings.length === 0 && !pendingAdd && (
              <p className="muted">暂无持仓，添加后会显示在下方。</p>
            )}
            {unknownSectorCount > 0 && (
              <div className="holding-toolbar">
                <p className="muted" style={{ margin: 0 }}>
                  有 {unknownSectorCount} 只持仓行业为「未知」
                </p>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => void backfillSectors()}
                  disabled={backfillingSectors}
                >
                  {backfillingSectors ? "补全中…" : "一键补全行业"}
                </button>
              </div>
            )}
            {holdings.map((h) => (
              <div className="holding-row" key={h.id ?? h.symbol}>
                <div>
                  <strong>{h.name}</strong>
                  <div className="muted">
                    {h.symbol} · 成本 {h.cost_price} 元/股 · {Math.round(h.quantity / 100)} 手 · {h.sector}
                  </div>
                </div>
                {h.id != null && (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={deletingId === h.id}
                    onClick={() => removeHolding(h.id!)}
                  >
                    {deletingId === h.id ? "删除中…" : "删除"}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {tab === "research" && (
          <div className="panel">
            <p className="muted" style={{ marginTop: 0 }}>
              基本面 / 技术面 / 情绪面 / 筹码面四维分析 + 多空辩论 + 裁判判定
            </p>
            <div className="holding-form holding-form-lookup">
              <label className="field">
                <span className="field-label">股票代码或名称</span>
                <input
                  placeholder="如 600519、贵州茅台"
                  value={researchQuery}
                  onChange={(e) => setResearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void lookupResearchStock();
                  }}
                />
              </label>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void lookupResearchStock()}
                disabled={lookingUpResearch || loadingResearch}
              >
                {lookingUpResearch ? "识别中…" : "识别股票"}
              </button>
            </div>
            {researchTarget && (
              <div className="confirm-card">
                <p>已选：{researchTarget.name}（{researchTarget.symbol}）</p>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => void runResearch(researchTarget.symbol, researchTarget.name)}
                  disabled={loadingResearch}
                >
                  {loadingResearch ? "多 Agent 投研中…" : "生成投研报告"}
                </button>
              </div>
            )}
            {holdings.length > 0 && (
              <div className="research-quick-picks">
                <span className="muted">从持仓快捷分析：</span>
                {holdings.map((h) => (
                  <button
                    key={h.symbol}
                    type="button"
                    className="btn btn-ghost"
                    disabled={loadingResearch}
                    onClick={() => void runResearch(h.symbol, h.name)}
                  >
                    {h.name}
                  </button>
                ))}
              </div>
            )}
            {loadingResearch && (
              <StreamFeed {...researchStream} />
            )}
            {researchReport && <ResearchReportView report={researchReport} />}
          </div>
        )}

        {tab === "risk" && (
          <div className="panel">
            <p className="muted" style={{ marginTop: 0 }}>
              简明风控摘要：规则扫描 → 快辩 → 裁判给出等级与仓位建议
            </p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void runRisk()}
              disabled={loadingRisk}
            >
              {loadingRisk ? "多 Agent 会诊中…" : "一键持仓体检"}
            </button>
            {(loadingRisk || riskStream.streamLog.length > 0) && (
              <StreamFeed {...riskStream} />
            )}
            {risk && risk.alerts.length > 0 && (
              <>
                {risk.alerts.map((a, i) => (
                  <div className={`card alert-${a.severity}`} key={i}>
                    <strong>{a.rule_id}</strong>
                    <MarkdownContent text={a.human_message || a.message} />
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

function CardView({ card }: { card: ChatResponse["cards"][0] }) {
  if (card.type === "research") {
    return <ResearchReportView report={card.data as unknown as ResearchReport} />;
  }
  if (card.type === "risk") {
    const d = card.data as unknown as RiskCheckup;
    return (
      <div className="card">
        <h4>风控体检</h4>
        <div><MarkdownContent text={d.portfolio_summary} /></div>
        {d.alerts.map((a, i) => (
          <p key={i} className={`alert-${a.severity}`}>
            <MarkdownContent text={a.human_message} />
          </p>
        ))}
      </div>
    );
  }
  if (card.type === "news") {
    const items = (card.data as { items: NewsItem[] }).items || [];
    return (
      <div className="card">
        <h4>相关快讯</h4>
        {items.map((n, i) => (
          <div key={i} className="news-card-item">
            <strong>{n.title}</strong>
            <MarkdownContent text={n.summary} />
          </div>
        ))}
      </div>
    );
  }
  return null;
}

function ResearchReportView({ report }: { report: ResearchReport }) {
  return (
    <div className="card research-report" style={{ marginTop: 16 }}>
      <h4>投研报告 · {report.name} ({report.symbol})</h4>
      <p className="research-meta">
        综合 {report.composite_score}/10 · 倾向 {report.bias}
      </p>
      <MarkdownContent text={report.summary} />
      <div className="stream-messages report-messages">
        {Object.entries(report.dimensions).map(([name, dim]) => (
          <div className="message assistant stream-msg" key={name}>
            <div className="stream-msg-head">
              <strong>{name} · {dim.score}/10</strong>
            </div>
            {dim.highlights.length > 0 && (
              <div className="stream-msg-body muted">
                <strong>亮点</strong>
                <MarkdownContent text={dim.highlights.join("\n\n")} />
              </div>
            )}
            {dim.risks.length > 0 && (
              <div className="stream-msg-body muted">
                <strong>风险</strong>
                <MarkdownContent text={dim.risks.join("\n\n")} />
              </div>
            )}
          </div>
        ))}
      </div>
      {report.debate && <DebateView debate={report.debate} />}
    </div>
  );
}

function DebateView({ debate }: { debate: ResearchReport["debate"] }) {
  if (!debate) return null;
  return (
    <div className="stream-messages report-messages">
      {debate.rounds.map((round) => (
        <div key={round.round}>
          {round.bull_argument && (
            <div className="message assistant stream-msg stream-role-bull">
              <div className="stream-msg-head"><strong>第 {round.round} 轮 · 看多</strong></div>
              <div className="stream-msg-body markdown-body">
                <MarkdownContent text={round.bull_argument} />
              </div>
            </div>
          )}
          {round.bear_rebuttal && (
            <div className="message assistant stream-msg stream-role-bear">
              <div className="stream-msg-head"><strong>第 {round.round} 轮 · 看空</strong></div>
              <div className="stream-msg-body markdown-body">
                <MarkdownContent text={round.bear_rebuttal} />
              </div>
            </div>
          )}
        </div>
      ))}
      <div className="message assistant stream-msg stream-judge">
        <div className="stream-msg-head">
          <strong>裁判 · {debate.final_bias} · 置信 {debate.confidence}</strong>
        </div>
        {debate.vote_tally && (
          <p className="stream-msg-body muted">
            Battle 投票 · 偏多 {debate.vote_tally["偏多"] ?? 0} · 偏空 {debate.vote_tally["偏空"] ?? 0} · 中性 {debate.vote_tally["中性"] ?? 0}
          </p>
        )}
        {debate.manager_thesis && (
          <div className="stream-msg-body muted">
            <strong>Research Manager</strong>
            <MarkdownContent text={debate.manager_thesis} />
          </div>
        )}
        <div className="stream-msg-body markdown-body">
          <MarkdownContent text={debate.judge_verdict} />
        </div>
        <div className="stream-msg-body muted">
          <MarkdownContent text={`共识：${debate.consensus}`} />
        </div>
        <div className="stream-msg-body muted">
          <MarkdownContent text={`分歧：${debate.core_divergence}`} />
        </div>
      </div>
    </div>
  );
}
