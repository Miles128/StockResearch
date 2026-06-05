import { useEffect, useMemo, useState } from "react";
import { api, AgentStreamEvent, ChatResponse, HoldingEnriched, NewsItem, ResearchReport, RiskCheckup, StockLookupOut } from "./api";
import { formatPrice, formatSignedMoney, formatSignedPct, signedClass } from "./holdingDisplay";
import { AboutPanel } from "./AboutPanel";
import { SettingsPanel } from "./SettingsPanel";
import { StreamFeed } from "./StreamFeed";
import { isLlmConfigured } from "./llmSettings";
import { applyStreamEvent, emptyStreamState, type StreamState } from "./streamEvents";
import { useI18n } from "./i18n";

type Tab = "chat" | "news" | "portfolio" | "risk";

interface Message {
  role: "user" | "assistant";
  content: string;
  cards?: ChatResponse["cards"];
  /** 完整 Multi-Agent 思考过程（SSE 过程快照，完成后保留） */
  process?: StreamState;
}

function TabNav({
  className,
  tab,
  onTab,
  items,
  ariaLabel,
  compact = false,
}: {
  className: string;
  tab: Tab;
  onTab: (key: Tab) => void;
  items: { key: Tab; label: string; fn: string }[];
  ariaLabel: string;
  /** 窄屏：隐藏 F1–F4，仅横向文字标签 */
  compact?: boolean;
}) {
  return (
    <nav className={className} aria-label={ariaLabel}>
      {items.map((n) => (
        <button
          key={n.key}
          type="button"
          className={`nav-btn${tab === n.key ? " active" : ""}`}
          onClick={() => onTab(n.key)}
          aria-keyshortcuts={compact ? undefined : n.fn}
        >
          {!compact && <span className="fn-key">{n.fn}</span>}
          <span className="nav-label">{n.label}</span>
        </button>
      ))}
    </nav>
  );
}

export default function App() {
  const { t, locale, setLocale } = useI18n();
  const navItems = useMemo(
    () => [
      { key: "chat" as Tab, label: t("nav.chat"), fn: "F1" },
      { key: "news" as Tab, label: t("nav.news"), fn: "F2" },
      { key: "portfolio" as Tab, label: t("nav.portfolio"), fn: "F3" },
      { key: "risk" as Tab, label: t("nav.risk"), fn: "F4" },
    ],
    [t, locale],
  );
  const pageTitles: Record<Tab, string> = {
    chat: t("page.chat"),
    news: t("page.news"),
    portfolio: t("page.portfolio"),
    risk: t("page.risk"),
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
  const [settingsOpen, setSettingsOpen] = useState(!isLlmConfigured());
  const [aboutOpen, setAboutOpen] = useState(false);
  const settingsRequired = !llmConfigured;

  function closeSettings() {
    if (settingsRequired) return;
    setSettingsOpen(false);
  }

  function handleLlmConfigured() {
    setLlmConfigured(true);
    setSettingsOpen(false);
  }

  useEffect(() => {
    const id = setInterval(() => {
      const now = new Date();
      setClock(now.toLocaleTimeString(locale === "zh" ? "zh-CN" : "en-US", { hour12: false }));
    }, 1000);
    return () => clearInterval(id);
  }, [locale]);

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
    } catch (e) {
      showError(String(e));
    } finally {
      setHoldingsLoading(false);
    }
  }

  async function executeChat(query: string) {
    setLoading(true);
    setStatusMsg(t("chat.connecting"));
    setChatStream(emptyStreamState());
    let processSnapshot = emptyStreamState();
    try {
      const resp = await api.chatStream(query, sessionId, (event: AgentStreamEvent) => {
        if (event.type === "analysis_choice") return;
        setChatStream((prev) => {
          const next = applyStreamEvent(prev, event);
          processSnapshot = next;
          return next;
        });
        if (event.type === "status" && event.message) {
          setStatusMsg(event.message);
        }
      });
      if (resp) {
        setSessionId(resp.session_id);
        processSnapshot = {
          ...processSnapshot,
          streamStatus: processSnapshot.streamStatus || statusMsg || t("chat.analysisDone"),
        };
        const assistantMsg: Message = {
          role: "assistant",
          content: resp.reply,
          cards: resp.cards,
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
        const resp = await api.chat(query, sessionId);
        setSessionId(resp.session_id);
        setMessages((m) => [
          ...m,
          { role: "assistant", content: resp.reply, cards: resp.cards },
        ]);
      } catch (e) {
        setMessages((m) => [...m, { role: "assistant", content: `Error: ${String(e)}` }]);
      }
    } finally {
      setLoading(false);
      setStatusMsg("");
    }
  }

  function sendChat() {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", content: userMsg }]);
    void executeChat(userMsg);
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
        if (cost <= 0) { showError(t("portfolio.invalidCost")); return; }
        await api.addHolding({ symbol: result.symbol, name: result.name, cost_price: cost, lots, sector: result.sector || undefined, buy_date: holdingDate || undefined });
        await loadHoldings();
        setHoldingInput(""); setHoldingCost(""); setHoldingLots(""); setHoldingDate(""); setLookupResult(null);
      }
    } catch (e) { showError(String(e)); } finally { setLookupLoading(false); }
  }

  async function confirmCandidate(symbol: string, name: string) {
    const cost = holdingCost ? parseFloat(holdingCost) : 0;
    const lots = holdingLots ? parseInt(holdingLots) : 1;
    if (cost <= 0) { showError(t("portfolio.invalidCost")); return; }
    try {
      await api.addHolding({ symbol, name, cost_price: cost, lots, buy_date: holdingDate || undefined });
      await loadHoldings();
      setHoldingInput(""); setHoldingCost(""); setHoldingLots(""); setHoldingDate(""); setLookupResult(null);
    } catch (e) { showError(String(e)); }
  }

  async function deleteHolding(id: number) {
    try { await api.deleteHolding(id); await loadHoldings(); } catch (e) { showError(String(e)); }
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
      />
      <div className="terminal-header">
        <div className="terminal-brand">
          <span className="bbg-logo">StockResearch</span>
          <span className="bbg-tag">{t("brand.tagline")}</span>
        </div>
        <div className="terminal-meta">
          <button
            type="button"
            className="locale-toggle"
            onClick={() => setLocale(locale === "zh" ? "en" : "zh")}
            title={locale === "zh" ? "English" : "中文"}
            aria-label={locale === "zh" ? "Switch to English" : "切换为中文"}
          >
            {locale === "zh" ? "EN" : "中"}
          </button>
          <button
            type="button"
            className="terminal-settings-btn"
            onClick={() => setAboutOpen(true)}
            title={t("header.aboutTitle")}
          >
            {t("header.about")}
          </button>
          <button
            type="button"
            className="terminal-settings-btn"
            onClick={() => setSettingsOpen(true)}
            disabled={settingsRequired}
            title={t("header.settingsTitle")}
          >
            {t("header.settings")}
          </button>
          <span className="terminal-clock">{clock}</span>
        </div>
      </div>
      <AboutPanel open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <SettingsPanel
        open={settingsOpen}
        onClose={closeSettings}
        required={settingsRequired}
        onConfigured={handleLlmConfigured}
      />

      <div className={`app-body${settingsRequired ? " app-locked" : ""}`}>
        <aside className="sidebar">
          <div className="brand">StockResearch</div>
          <div className="brand-sub">{t("brand.tagline")}</div>
          <TabNav className="tab-nav-desktop" tab={tab} onTab={setTab} items={navItems} ariaLabel={t("nav.aria")} />
        </aside>

        <div className="main">
          {error && <div className="error">{error}</div>}

          <div className="topbar">
            <h2 className="page-title">{pageTitles[tab]}</h2>
            <span className="page-sub">{tab.toUpperCase()}</span>
          </div>

          {tab === "chat" && (
            <div className="panel chat-panel">
              <div className="chat-messages">
                {messages.map((m, i) => (
                  <div key={i} className="chat-turn">
                    {m.role === "user" ? (
                      <div className="message user">
                        <div
                          className="markdown-body"
                          dangerouslySetInnerHTML={{ __html: simpleMarkdown(m.content) }}
                        />
                      </div>
                    ) : (
                      <>
                        {m.process && (
                          <div className="message assistant process-panel">
                            <p className="process-panel-title">{t("chat.processTitle")}</p>
                            <StreamFeed
                              streamStatus={m.process.streamStatus}
                              streamLog={m.process.streamLog}
                              agentSteps={m.process.agentSteps}
                              debateRounds={m.process.debateRounds}
                              judgeVerdict={m.process.judgeVerdict}
                              voteTally={m.process.voteTally}
                              activeStreamIds={[]}
                            />
                          </div>
                        )}
                        {m.content.trim() && (
                          <div className="message assistant">
                            <p className="process-panel-title">{t("chat.conclusion")}</p>
                            <div
                              className="markdown-body"
                              dangerouslySetInnerHTML={{ __html: simpleMarkdown(m.content) }}
                            />
                          </div>
                        )}
                        {m.cards?.map((c, j) => (
                          <CardView key={j} card={c} />
                        ))}
                      </>
                    )}
                  </div>
                ))}
                {loading && (
                  <div className="message assistant stream-live-panel">
                    <p className="process-panel-title">{t("chat.processLive")}</p>
                    <StreamFeed
                      streamStatus={chatStream.streamStatus || statusMsg}
                      streamLog={chatStream.streamLog}
                      agentSteps={chatStream.agentSteps}
                      debateRounds={chatStream.debateRounds}
                      judgeVerdict={chatStream.judgeVerdict}
                      voteTally={chatStream.voteTally}
                      activeStreamIds={chatStream.activeStreamIds}
                    />
                  </div>
                )}
              </div>
              <div className="chat-footer">
                <div className="chat-input-row">
                  <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && sendChat()} placeholder={t("chat.placeholder")} />
                  <button className="btn btn-primary" onClick={sendChat} disabled={loading}>{loading ? t("chat.sending") : t("chat.send")}</button>
                </div>
                <p className="disclaimer">{t("chat.disclaimer")}</p>
              </div>
            </div>
          )}

          {tab === "news" && (
            <div className="panel">
              <button className="btn btn-primary" onClick={loadNews} disabled={newsLoading}>
                {newsLoading ? t("news.loading") : t("news.refresh")}
              </button>
              {news.map((n, i) => (
                <div className="card" key={i}>
                  <h4>{n.title}</h4>
                  <p>{n.summary}</p>
                  <span className={`stat-pill ${n.sentiment === "bullish" ? "up" : n.sentiment === "bearish" ? "down" : ""}`}>
                    {n.sentiment} · {n.impact_level} {n.related_to_user ? `· ${t("news.related")}` : ""}
                  </span>
                </div>
              ))}
            </div>
          )}

          {tab === "portfolio" && (
            <div className="panel">
              <div className="holding-form">
                <div className="field">
                  <span className="field-label">{t("portfolio.symbol")}</span>
                  <input placeholder={t("portfolio.symbolPh")} value={holdingInput} onChange={(e) => { setHoldingInput(e.target.value); setLookupResult(null); }} onKeyDown={(e) => e.key === "Enter" && lookupAndAdd()} />
                </div>
                <div className="field">
                  <span className="field-label">{t("portfolio.cost")}</span>
                  <input type="number" placeholder="0.00" value={holdingCost} onChange={(e) => setHoldingCost(e.target.value)} />
                </div>
                <div className="field">
                  <span className="field-label">{t("portfolio.lots")}</span>
                  <input type="number" placeholder="1" value={holdingLots} onChange={(e) => setHoldingLots(e.target.value)} />
                </div>
                <div className="field">
                  <span className="field-label">{t("portfolio.buyDate")}</span>
                  <input
                    type="date"
                    value={holdingDate}
                    max={new Date().toISOString().slice(0, 10)}
                    title={t("portfolio.buyDateTitle")}
                    onChange={(e) => setHoldingDate(e.target.value)}
                  />
                </div>
                <button className="btn btn-primary" onClick={lookupAndAdd} disabled={lookupLoading} style={{ alignSelf: "end" }}>
                  {lookupLoading ? t("portfolio.querying") : t("portfolio.add")}
                </button>
              </div>
              {lookupResult && lookupResult.status === "ambiguous" && (
                <div className="confirm-card">
                  <span className="field-label">{t("portfolio.pickStock")}</span>
                  <div className="candidate-list">
                    {lookupResult.candidates.map((c) => (
                      <button key={c.symbol} className="btn btn-ghost" onClick={() => confirmCandidate(c.symbol, c.name)}>
                        {c.name} ({c.symbol})
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div className="holding-toolbar">
                <span className="muted">
                  {holdingsLoading
                    ? t("portfolio.quotesUpdating")
                    : holdings[0]?.market_session === "trading"
                      ? t("portfolio.trading")
                      : t("portfolio.closed")}
                </span>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => void loadHoldings()} disabled={holdingsLoading}>
                  {t("portfolio.refresh")}
                </button>
              </div>
              {holdings.length === 0 ? (
                <p className="muted holdings-empty">{t("portfolio.empty")}</p>
              ) : (
                <div className="holdings-table-wrap">
                  <table className="holdings-table">
                    <thead>
                      <tr>
                        <th>{t("portfolio.stock")}</th>
                        <th>{t("portfolio.price")}</th>
                        <th>{t("portfolio.change")}</th>
                        <th>{t("portfolio.costCol")}</th>
                        <th>{t("portfolio.qty")}</th>
                        <th>{t("portfolio.pnl")}</th>
                        <th>{t("portfolio.annualized")}</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {holdings.map((h) => (
                        <tr key={h.id}>
                          <td>
                            <div className="holding-name">{h.name}</div>
                            <div className="holding-meta muted">
                              {h.symbol} · {h.sector}
                              {h.buy_date ? ` · ${h.buy_date}` : ""}
                            </div>
                          </td>
                          <td className="mono">
                            {h.quote_available ? (
                              <>
                                <span className="holding-price-label muted">{h.price_label}</span>{" "}
                                {formatPrice(h.price ?? null)}
                              </>
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                          <td className={`mono ${signedClass(h.change_pct)}`}>
                            {h.quote_available ? formatSignedPct(h.change_pct ?? null) : "—"}
                          </td>
                          <td className="mono">{h.cost_price.toFixed(2)}</td>
                          <td className="mono">{h.quantity}</td>
                          <td className={signedClass(h.profit_pct)}>
                            {h.quote_available ? (
                              <>
                                <div className="mono">{formatSignedMoney(h.profit_amount ?? null)}</div>
                                <div className="mono holdings-sub">{formatSignedPct(h.profit_pct ?? null)}</div>
                              </>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td className={`mono ${signedClass(h.annualized_pct)}`}>
                            {h.annualized_pct != null ? formatSignedPct(h.annualized_pct) : "—"}
                          </td>
                          <td>
                            <button type="button" className="delete-btn" onClick={() => h.id && deleteHolding(h.id)}>
                              DEL
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {tab === "risk" && (
            <div className="panel">
              <button className="btn btn-primary" onClick={runRisk} disabled={loading}>
                {loading ? t("risk.running") : t("risk.run")}
              </button>
              {risk && (
                <>
                  <p style={{ margin: "8px 0" }}>{risk.portfolio_summary}</p>

                  {/* Risk Metrics Table */}
                  {risk.metrics && (
                    <div className="card">
                      <h4>{t("risk.metrics")}</h4>
                      <table className="metrics-table">
                        <tbody>
                          <tr><td>{t("risk.sharpe")}</td><td className="mono">{risk.metrics.sharpe_ratio.toFixed(2)}</td><td className="muted">{ratioGrade(risk.metrics.sharpe_ratio, 2, 1)}</td></tr>
                          <tr><td>{t("risk.sortino")}</td><td className="mono">{risk.metrics.sortino_ratio.toFixed(2)}</td><td className="muted">{ratioGrade(risk.metrics.sortino_ratio, 2, 1)}</td></tr>
                          <tr><td>{t("risk.calmar")}</td><td className="mono">{risk.metrics.calmar_ratio.toFixed(2)}</td><td className="muted">{ratioGrade(risk.metrics.calmar_ratio, 3, 1)}</td></tr>
                          <tr><td>{t("risk.infoRatio")}</td><td className="mono">{risk.metrics.information_ratio.toFixed(2)}</td><td className="muted">{ratioGrade(risk.metrics.information_ratio, 1, 0.5)}</td></tr>
                          <tr><td>{t("risk.maxDrawdown")}</td><td className={`mono ${risk.metrics.max_drawdown < -0.1 ? "down" : risk.metrics.max_drawdown < 0 ? "warn" : ""}`}>{(risk.metrics.max_drawdown * 100).toFixed(2)}%</td><td className="muted">{Math.abs(risk.metrics.max_drawdown) > 0.15 ? t("rating.highRisk") : Math.abs(risk.metrics.max_drawdown) > 0.08 ? t("rating.watch") : t("rating.ok")}</td></tr>
                          <tr><td>{t("risk.volatility")}</td><td className="mono">{(risk.metrics.volatility * 100).toFixed(2)}%</td><td className="muted">{risk.metrics.volatility > 0.3 ? t("rating.high") : risk.metrics.volatility > 0.2 ? t("rating.medium") : t("rating.low")}</td></tr>
                          <tr><td>{t("risk.concentration")}</td><td className="mono">{(risk.metrics.concentration_ratio * 100).toFixed(1)}%</td><td className="muted">{risk.metrics.concentration_sector || "-"} {risk.metrics.concentration_ratio > 0.4 ? t("rating.elevated") : t("rating.diversified")}</td></tr>
                          <tr><td>{t("risk.maxLoss1d")}</td><td className="mono down">¥{risk.metrics.max_loss_1d.toLocaleString(numLocale, { minimumFractionDigits: 2 })}</td><td className="muted">{(risk.metrics.max_loss_1d_pct * 100).toFixed(2)}% (3σ)</td></tr>
                          <tr><td>{t("risk.expectedLoss")}</td><td className="mono down">¥{risk.metrics.expected_loss.toLocaleString(numLocale, { minimumFractionDigits: 2 })}</td><td className="muted">{(risk.metrics.expected_loss_pct * 100).toFixed(2)}% (PD×LGD×EAD)</td></tr>
                        </tbody>
                      </table>
                      {risk.metrics.individual_drawdowns.length > 0 && (
                        <>
                          <h4 style={{ marginTop: 10 }}>{t("risk.stockDrawdown")}</h4>
                          <table className="metrics-table">
                            <thead><tr><th>{t("risk.stock")}</th><th>{t("portfolio.costCol")}</th><th>{t("risk.current")}</th><th>{t("risk.drawdown")}</th></tr></thead>
                            <tbody>
                              {risk.metrics.individual_drawdowns.map((d: any, i: number) => (
                                <tr key={i}>
                                  <td>{d.name}</td>
                                  <td className="mono">{d.cost_price?.toFixed(2)}</td>
                                  <td className="mono">{d.current_price?.toFixed(2)}</td>
                                  <td className={`mono ${d.drawdown_pct < -0.08 ? "down" : d.drawdown_pct < 0 ? "warn" : ""}`}>{((d.drawdown_pct ?? 0) * 100).toFixed(2)}%</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </>
                      )}
                    </div>
                  )}

                  {/* VaR Display */}
                  {risk.var_result && (
                    <div className="card">
                      <h4>{t("risk.var")}</h4>
                      <div className="stat-row">
                        <span className="stat-pill">{t("risk.confidence")} {(risk.var_result.confidence_level * 100).toFixed(0)}%</span>
                        <span className="stat-pill">{t("risk.horizon")} {risk.var_result.time_horizon_days}{t("risk.days")}</span>
                        <span className="stat-pill">{t("risk.method")} {risk.var_result.method}</span>
                      </div>
                      <div className="var-display">
                        <div className="var-main">
                          <span className="var-label">{t("risk.varAbs")}</span>
                          <span className="var-value down">¥{risk.var_result.var_value.toLocaleString(numLocale, { minimumFractionDigits: 2 })}</span>
                        </div>
                        <div className="var-main">
                          <span className="var-label">{t("risk.varPct")}</span>
                          <span className="var-value">{(risk.var_result.var_pct * 100).toFixed(2)}%</span>
                        </div>
                        <div className="var-main">
                          <span className="var-label">{t("risk.cvar")}</span>
                          <span className="var-value down">¥{risk.var_result.cvar_value.toLocaleString(numLocale, { minimumFractionDigits: 2 })}</span>
                        </div>
                        <div className="var-main">
                          <span className="var-label">{t("risk.cvarPct")}</span>
                          <span className="var-value">{(risk.var_result.cvar_pct * 100).toFixed(2)}%</span>
                        </div>
                      </div>
                      {/* VaR bar visualization */}
                      <div className="var-bar-container">
                        <div className="var-bar-track">
                          <div className="var-bar-fill" style={{ width: `${Math.min(risk.var_result.var_pct * 100 * 2, 100)}%` }} />
                        </div>
                        <div className="var-bar-labels">
                          <span>0%</span>
                          <span>{(risk.var_result.var_pct * 100).toFixed(1)}%</span>
                          <span>50%</span>
                        </div>
                      </div>
                      {risk.var_result.holdings_var.length > 0 && (
                        <table className="metrics-table" style={{ marginTop: 8 }}>
                          <thead><tr><th>{t("risk.stock")}</th><th>{t("risk.weight")}</th><th>VaR</th></tr></thead>
                          <tbody>
                            {risk.var_result.holdings_var.map((h: any, i: number) => (
                              <tr key={i}>
                                <td>{h.name}</td>
                                <td className="mono">{((h.weight ?? 0) * 100).toFixed(1)}%</td>
                                <td className="mono down">¥{(h.var_value ?? 0).toLocaleString(numLocale, { minimumFractionDigits: 2 })}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  )}

                  {/* Alerts */}
                  {risk.alerts.map((a, i) => (
                    <div className={`card alert-${a.severity}`} key={i}>
                      <h4>{a.rule_id}</h4>
                      <p>{a.human_message}</p>
                    </div>
                  ))}
                  {risk.llm_analysis && (
                    <div className="card">
                      <h4>{t("risk.aiAnalysis")}</h4>
                      <p><strong>{t("risk.market")}:</strong> {risk.llm_analysis.market_assessment}</p>
                      <p><strong>{t("risk.correlation")}:</strong> {risk.llm_analysis.correlation_analysis}</p>
                      <p><strong>{t("risk.narrative")}:</strong> {risk.llm_analysis.risk_narrative}</p>
                      {risk.llm_analysis.scenario_analysis.length > 0 && (
                        <>
                          <span className="field-label">{t("risk.scenarios")}</span>
                          <ul>{risk.llm_analysis.scenario_analysis.map((s, i) => <li key={i}>{s}</li>)}</ul>
                        </>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CardView({ card }: { card: ChatResponse["cards"][0] }) {
  const { t } = useI18n();
  try {
    if (card.type === "research" && card.data && "composite_score" in card.data) {
      const d = card.data as unknown as ResearchReport;
      return (
        <div className="card">
          <h4>{t("card.research")} · {d.name} ({d.symbol})</h4>
          <div className="stat-row">
            <span className="stat-pill">{t("card.score")} {d.composite_score}/10</span>
            <span className="stat-pill">{t("card.bias")} {d.bias}</span>
          </div>
          <p>{d.summary}</p>
        </div>
      );
    }
    if (card.type === "risk" && card.data && "portfolio_summary" in card.data) {
      const d = card.data as unknown as RiskCheckup;
      return (
        <div className="card">
          <h4>{t("card.riskCheckup")}</h4>
          <p>{d.portfolio_summary}</p>
          {d.alerts?.slice(0, 3).map((a, i) => (
            <p key={i} className={`alert-${a.severity}`}>{a.human_message}</p>
          ))}
          {d.llm_analysis && <p><strong>{t("card.aiBrief")}:</strong> {d.llm_analysis.risk_narrative}</p>}
        </div>
      );
    }
    if (card.type === "news" && card.data && "items" in card.data) {
      const items = (card.data as { items: NewsItem[] }).items || [];
      return (
        <div className="card">
          <h4>{t("card.relatedNews")}</h4>
          {items.slice(0, 3).map((n, i) => <p key={i}>{n.title} — {n.summary}</p>)}
        </div>
      );
    }
    if (card.type === "debate" && card.data && "positions" in card.data) {
      const d = card.data as { positions: { agent: string; stance: string; arguments: string }[]; vote_tally: Record<string, number>; final_bias: string; synthesis: string; symbol: string; name: string };
      const biasLabel: Record<string, string> = { bullish: t("card.bullish"), bearish: t("card.bearish"), neutral: t("card.neutral") };
      const stanceColor: Record<string, string> = { "看多": "up", "看空": "down", "中性": "", Long: "up", Short: "down", Neutral: "" };
      const stanceLabel = (s: string) =>
        ({ "看多": t("card.long"), "看空": t("card.short"), "中性": t("card.neutral") } as Record<string, string>)[s] ?? s;
      return (
        <div className="card">
          <h4>{t("card.debate")} · {d.name}({d.symbol})</h4>
          <div className="stat-row">
            <span className="stat-pill">{t("card.long")} {d.vote_tally["看多"] || 0}</span>
            <span className="stat-pill">{t("card.short")} {d.vote_tally["看空"] || 0}</span>
            <span className="stat-pill">{t("card.neutral")} {d.vote_tally["中性"] || 0}</span>
            <span className={`stat-pill ${d.final_bias === "bullish" ? "up" : d.final_bias === "bearish" ? "down" : ""}`}>{t("card.bias")} {biasLabel[d.final_bias] || d.final_bias}</span>
          </div>
          {d.positions.map((p, i) => (
            <div key={i} className={`debate-position ${stanceColor[p.stance] || ""}`}>
              <strong>{p.agent} {t("card.analyst")}</strong> <span className={`stat-pill ${stanceColor[p.stance]}`}>{stanceLabel(p.stance)}</span>
              <p className="muted" style={{ marginTop: 2 }}>{p.arguments.slice(0, 200)}{p.arguments.length > 200 ? "..." : ""}</p>
            </div>
          ))}
          {d.synthesis && (
            <div style={{ marginTop: 8, borderTop: "1px solid var(--bbg-border)", paddingTop: 8 }}>
              <strong>{t("card.judge")}</strong>
              <div className="markdown-body" style={{ marginTop: 4 }} dangerouslySetInnerHTML={{ __html: simpleMarkdown(d.synthesis) }} />
            </div>
          )}
        </div>
      );
    }
    if (card.type === "financial" && card.data && "ratios" in card.data) {
      const d = card.data as { symbol: string; name: string; ratios: { name: string; value: string; reference: string; assessment: string }[]; summary: string };
      return (
        <div className="card">
          <h4>{t("card.financial")} · {d.name}({d.symbol})</h4>
          <table className="metrics-table">
            <thead><tr><th>{t("card.metric")}</th><th>{t("card.value")}</th><th>{t("card.benchmark")}</th><th>{t("card.assessment")}</th></tr></thead>
            <tbody>
              {d.ratios.map((r, i) => (
                <tr key={i}>
                  <td>{r.name}</td>
                  <td className="mono">{r.value}</td>
                  <td className="muted">{r.reference}</td>
                  <td className={r.assessment.includes("高") || r.assessment.includes("过") ? "down" : r.assessment.includes("优") || r.assessment.includes("良") ? "up" : ""}>{r.assessment}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {d.summary && <div className="markdown-body" style={{ marginTop: 8 }} dangerouslySetInnerHTML={{ __html: simpleMarkdown(d.summary) }} />}
        </div>
      );
    }
    if (card.type === "plan" && card.data) {
      const d = card.data as { phase: string; reasoning?: string; steps?: { id: number; description: string }[]; step_id?: number; step?: string; result_preview?: string };
      if (d.phase === "plan") {
        return (
          <div className="card">
            <h4>{t("card.plan")}</h4>
            {d.reasoning && <p className="muted">{d.reasoning}</p>}
            <ol style={{ margin: "4px 0", paddingLeft: 20 }}>
              {d.steps?.map((s, i) => <li key={i}>{s.description}</li>)}
            </ol>
          </div>
        );
      }
      if (d.phase === "execute") {
        return (
          <div className="card" style={{ borderLeft: "2px solid var(--bbg-amber)" }}>
            <h4>{t("card.step")} {d.step_id}</h4>
            <p className="muted">{d.step}</p>
            {d.result_preview && <p style={{ marginTop: 4 }}>{d.result_preview}</p>}
          </div>
        );
      }
    }
    if (card.type === "text" && card.data && "content" in card.data) {
      const content = String((card.data as { content: string }).content || "");
      if (!content) return null;
      return (
        <div className="card">
          <div className="markdown-body" dangerouslySetInnerHTML={{ __html: simpleMarkdown(content) }} />
        </div>
      );
    }
  } catch {
    return <div className="card"><p>{t("card.parseError")}</p></div>;
  }
  return null;
}

function simpleMarkdown(text: string): string {
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Code blocks (```lang ... ```)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, lang: string, code: string) =>
    `<pre class="code-block"><code>${code.trim()}</code></pre>`
  );

  // Inline code
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Headers
  html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^## (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^# (.+)$/gm, "<h3>$1</h3>");

  // Bold & italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

  // Tables
  html = html.replace(/^(\|.+\|)\n(\|[-| :]+\|)\n((?:\|.+\|\n?)*)/gm, (_m, header: string, _sep: string, body: string) => {
    const thCells = header.split("|").filter((c: string) => c.trim()).map((c: string) => `<th>${c.trim()}</th>`).join("");
    const rows = body.trim().split("\n").map((row: string) => {
      const cells = row.split("|").filter((c: string) => c.trim()).map((c: string) => `<td>${c.trim()}</td>`).join("");
      return `<tr>${cells}</tr>`;
    }).join("");
    return `<table class="metrics-table"><thead><tr>${thCells}</tr></thead><tbody>${rows}</tbody></table>`;
  });

  // Unordered lists
  html = html.replace(/^[-•*] (.+)$/gm, "<li>$1</li>");
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, "<ul>$1</ul>");

  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");

  // Horizontal rule
  html = html.replace(/^---+$/gm, "<hr/>");

  // Paragraphs
  html = html.replace(/\n{2,}/g, "</p><p>");
  html = html.replace(/\n/g, "<br>");

  return `<p>${html}</p>`;
}
