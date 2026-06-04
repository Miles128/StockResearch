import { useEffect, useState } from "react";
import { api, AgentStreamEvent, AnalysisMode, ChatResponse, HoldingEnriched, NewsItem, ResearchReport, RiskCheckup, StockLookupOut } from "./api";
import { formatPrice, formatSignedMoney, formatSignedPct, signedClass } from "./holdingDisplay";
import { analysisModeLabel, shouldAskAnalysisMode } from "./chatAnalysis";
import { AboutPanel } from "./AboutPanel";
import { SettingsPanel } from "./SettingsPanel";
import { StreamFeed } from "./StreamFeed";
import { isLlmConfigured } from "./llmSettings";
import { applyStreamEvent, emptyStreamState, type StreamState } from "./streamEvents";

type Tab = "chat" | "news" | "portfolio" | "risk";

interface Message {
  role: "user" | "assistant";
  content: string;
  cards?: ChatResponse["cards"];
  /** 完整 Multi-Agent 思考过程（SSE 过程快照，完成后保留） */
  process?: StreamState;
  /** 等待用户选择简单 / 复杂分析 */
  pendingChoice?: { query: string };
}

const NAV: { key: Tab; label: string; fn: string }[] = [
  { key: "chat", label: "对话", fn: "F1" },
  { key: "news", label: "新闻", fn: "F2" },
  { key: "portfolio", label: "持仓", fn: "F3" },
  { key: "risk", label: "风控", fn: "F4" },
];

export default function App() {
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
      setClock(now.toLocaleTimeString("zh-CN", { hour12: false }));
    }, 1000);
    return () => clearInterval(id);
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
    } catch (e) {
      showError(String(e));
    } finally {
      setHoldingsLoading(false);
    }
  }

  async function executeChat(query: string, analysisMode?: AnalysisMode, replaceIndex?: number) {
    setLoading(true);
    setStatusMsg("正在连接…");
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
      }, analysisMode);
      if (resp) {
        setSessionId(resp.session_id);
        processSnapshot = {
          ...processSnapshot,
          streamStatus: processSnapshot.streamStatus || statusMsg || "分析完成",
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
        if (replaceIndex !== undefined) {
          setMessages((m) => m.map((msg, i) => (i === replaceIndex ? assistantMsg : msg)));
        } else {
          setMessages((m) => [...m, assistantMsg]);
        }
      }
    } catch {
      try {
        setStatusMsg("流式连接失败，切换同步模式…");
        const resp = await api.chat(query, sessionId, analysisMode);
        setSessionId(resp.session_id);
        const assistantMsg: Message = {
          role: "assistant",
          content: resp.reply,
          cards: resp.cards,
        };
        if (replaceIndex !== undefined) {
          setMessages((m) => m.map((msg, i) => (i === replaceIndex ? assistantMsg : msg)));
        } else {
          setMessages((m) => [...m, assistantMsg]);
        }
      } catch (e) {
        const errMsg: Message = { role: "assistant", content: `Error: ${String(e)}` };
        if (replaceIndex !== undefined) {
          setMessages((m) => m.map((msg, i) => (i === replaceIndex ? errMsg : msg)));
        } else {
          setMessages((m) => [...m, errMsg]);
        }
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
    if (shouldAskAnalysisMode(userMsg)) {
      setMessages((m) => [
        ...m,
        { role: "user", content: userMsg },
        { role: "assistant", content: "", pendingChoice: { query: userMsg } },
      ]);
      return;
    }
    void executeChat(userMsg);
  }

  function chooseAnalysisMode(query: string, mode: AnalysisMode, msgIndex: number) {
    if (loading) return;
    setMessages((m) =>
      m.map((msg, i) =>
        i === msgIndex
          ? {
              role: "assistant",
              content: `已选择：${analysisModeLabel(mode)}，正在分析…`,
              pendingChoice: undefined,
            }
          : msg,
      ),
    );
    void executeChat(query, mode, msgIndex);
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
        if (cost <= 0) { showError("请输入有效的成本价"); return; }
        await api.addHolding({ symbol: result.symbol, name: result.name, cost_price: cost, lots, sector: result.sector || undefined, buy_date: holdingDate || undefined });
        await loadHoldings();
        setHoldingInput(""); setHoldingCost(""); setHoldingLots(""); setHoldingDate(""); setLookupResult(null);
      }
    } catch (e) { showError(String(e)); } finally { setLookupLoading(false); }
  }

  async function confirmCandidate(symbol: string, name: string) {
    const cost = holdingCost ? parseFloat(holdingCost) : 0;
    const lots = holdingLots ? parseInt(holdingLots) : 1;
    if (cost <= 0) { showError("请输入有效的成本价"); return; }
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
      <div className="terminal-header">
        <div className="terminal-brand">
          <span className="bbg-logo">StockResearch</span>
          <span className="bbg-tag">AI 投研终端</span>
        </div>
        <div className="terminal-meta">
          <span className="terminal-source">AKSHARE</span>
          <button
            type="button"
            className="terminal-settings-btn"
            onClick={() => setAboutOpen(true)}
            title="关于作者与参考项目"
          >
            关于
          </button>
          <button
            type="button"
            className="terminal-settings-btn"
            onClick={() => setSettingsOpen(true)}
            disabled={settingsRequired}
            title="大模型 API Key / 模型 / 温度"
          >
            设置
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
        <div className="sidebar">
          <div className="brand">StockResearch</div>
          <div className="brand-sub">AI 投研终端</div>
          {NAV.map((n) => (
            <button key={n.key} className={`nav-btn${tab === n.key ? " active" : ""}`} onClick={() => setTab(n.key)}>
              <span className="fn-key">{n.fn}</span> {n.label}
            </button>
          ))}
        </div>

        <div className="main">
          {error && <div className="error">{error}</div>}

          <div className="topbar">
            <h2 className="page-title">{{ chat: "智能对话", news: "新闻快讯", portfolio: "持仓管理", risk: "风控体检" }[tab]}</h2>
            <span className="page-sub">{tab.toUpperCase()}</span>
          </div>

          {tab === "chat" && (
            <div className="panel">
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
                    ) : m.pendingChoice ? (
                      <div className="message assistant analysis-choice-panel">
                        <p className="analysis-choice-title">请选择分析深度</p>
                        <p className="analysis-choice-sub">针对：{m.pendingChoice.query}</p>
                        <div className="analysis-choice-actions">
                          <button
                            type="button"
                            className="btn btn-ghost analysis-choice-btn"
                            disabled={loading}
                            onClick={() => chooseAnalysisMode(m.pendingChoice!.query, "simple", i)}
                          >
                            简单分析
                          </button>
                          <button
                            type="button"
                            className="btn btn-primary analysis-choice-btn"
                            disabled={loading}
                            onClick={() => chooseAnalysisMode(m.pendingChoice!.query, "complex", i)}
                          >
                            复杂分析
                          </button>
                        </div>
                        <p className="analysis-choice-hint">
                          简单：快速直接回答；复杂：Multi-Agent 投研、多空辩论或规划执行
                        </p>
                      </div>
                    ) : (
                      <>
                        {m.process && (
                          <div className="message assistant process-panel">
                            <p className="process-panel-title">Multi-Agent 思考过程</p>
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
                            <p className="process-panel-title">综合结论</p>
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
                    <p className="process-panel-title">Multi-Agent 思考过程（进行中）</p>
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
              <div className="chat-input-row">
                <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && sendChat()} placeholder="输入消息，如：帮我分析一下贵州茅台" />
                <button className="btn btn-primary" onClick={sendChat} disabled={loading}>{loading ? "分析中..." : "发送"}</button>
              </div>
              <p className="disclaimer">以上内容由 AI 生成，仅供参考，不构成投资建议。</p>
            </div>
          )}

          {tab === "news" && (
            <div className="panel">
              <button className="btn btn-primary" onClick={loadNews} disabled={newsLoading}>
                {newsLoading ? "加载中..." : "刷新快讯"}
              </button>
              {news.map((n, i) => (
                <div className="card" key={i}>
                  <h4>{n.title}</h4>
                  <p>{n.summary}</p>
                  <span className={`stat-pill ${n.sentiment === "bullish" ? "up" : n.sentiment === "bearish" ? "down" : ""}`}>
                    {n.sentiment} · {n.impact_level} {n.related_to_user ? "· 与你相关" : ""}
                  </span>
                </div>
              ))}
            </div>
          )}

          {tab === "portfolio" && (
            <div className="panel">
              <div className="holding-form">
                <div className="field">
                  <span className="field-label">代码/名称</span>
                  <input placeholder="如 600519 或 贵州茅台" value={holdingInput} onChange={(e) => { setHoldingInput(e.target.value); setLookupResult(null); }} onKeyDown={(e) => e.key === "Enter" && lookupAndAdd()} />
                </div>
                <div className="field">
                  <span className="field-label">成本价</span>
                  <input type="number" placeholder="0.00" value={holdingCost} onChange={(e) => setHoldingCost(e.target.value)} />
                </div>
                <div className="field">
                  <span className="field-label">手数</span>
                  <input type="number" placeholder="1" value={holdingLots} onChange={(e) => setHoldingLots(e.target.value)} />
                </div>
                <div className="field">
                  <span className="field-label">买入日期</span>
                  <input
                    type="date"
                    value={holdingDate}
                    max={new Date().toISOString().slice(0, 10)}
                    title="须为 A 股交易日（有开盘的日期）"
                    onChange={(e) => setHoldingDate(e.target.value)}
                  />
                </div>
                <button className="btn btn-primary" onClick={lookupAndAdd} disabled={lookupLoading} style={{ alignSelf: "end" }}>
                  {lookupLoading ? "查询中..." : "添加"}
                </button>
              </div>
              {lookupResult && lookupResult.status === "ambiguous" && (
                <div className="confirm-card">
                  <span className="field-label">请选择股票</span>
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
                    ? "行情更新中…"
                    : holdings[0]?.market_session === "trading"
                      ? "盘中 · 显示现价（每 30 秒刷新）"
                      : "已收盘 · 显示收盘价"}
                </span>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => void loadHoldings()} disabled={holdingsLoading}>
                  刷新
                </button>
              </div>
              {holdings.length === 0 ? (
                <p className="muted holdings-empty">暂无持仓，请在上方添加</p>
              ) : (
                <div className="holdings-table-wrap">
                  <table className="holdings-table">
                    <thead>
                      <tr>
                        <th>股票</th>
                        <th>价格</th>
                        <th>涨跌</th>
                        <th>成本</th>
                        <th>数量</th>
                        <th>盈亏</th>
                        <th>年化</th>
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
                {loading ? "体检中..." : "持仓体检"}
              </button>
              {risk && (
                <>
                  <p style={{ margin: "8px 0" }}>{risk.portfolio_summary}</p>

                  {/* Risk Metrics Table */}
                  {risk.metrics && (
                    <div className="card">
                      <h4>风险指标</h4>
                      <table className="metrics-table">
                        <tbody>
                          <tr><td>夏普比率</td><td className="mono">{risk.metrics.sharpe_ratio.toFixed(2)}</td><td className="muted">{risk.metrics.sharpe_ratio > 2 ? "优" : risk.metrics.sharpe_ratio > 1 ? "良" : risk.metrics.sharpe_ratio > 0 ? "中" : "差"}</td></tr>
                          <tr><td>索提诺比率</td><td className="mono">{risk.metrics.sortino_ratio.toFixed(2)}</td><td className="muted">{risk.metrics.sortino_ratio > 2 ? "优" : risk.metrics.sortino_ratio > 1 ? "良" : risk.metrics.sortino_ratio > 0 ? "中" : "差"}</td></tr>
                          <tr><td>Calmar 比率</td><td className="mono">{risk.metrics.calmar_ratio.toFixed(2)}</td><td className="muted">{risk.metrics.calmar_ratio > 3 ? "优" : risk.metrics.calmar_ratio > 1 ? "良" : risk.metrics.calmar_ratio > 0 ? "中" : "差"}</td></tr>
                          <tr><td>信息比率</td><td className="mono">{risk.metrics.information_ratio.toFixed(2)}</td><td className="muted">{risk.metrics.information_ratio > 1 ? "优" : risk.metrics.information_ratio > 0.5 ? "良" : risk.metrics.information_ratio > 0 ? "中" : "差"}</td></tr>
                          <tr><td>最大回撤</td><td className={`mono ${risk.metrics.max_drawdown < -0.1 ? "down" : risk.metrics.max_drawdown < 0 ? "warn" : ""}`}>{(risk.metrics.max_drawdown * 100).toFixed(2)}%</td><td className="muted">{Math.abs(risk.metrics.max_drawdown) > 0.15 ? "高危" : Math.abs(risk.metrics.max_drawdown) > 0.08 ? "关注" : "可控"}</td></tr>
                          <tr><td>年化波动率</td><td className="mono">{(risk.metrics.volatility * 100).toFixed(2)}%</td><td className="muted">{risk.metrics.volatility > 0.3 ? "高" : risk.metrics.volatility > 0.2 ? "中" : "低"}</td></tr>
                          <tr><td>行业集中度</td><td className="mono">{(risk.metrics.concentration_ratio * 100).toFixed(1)}%</td><td className="muted">{risk.metrics.concentration_sector || "-"} {risk.metrics.concentration_ratio > 0.4 ? "偏高" : "分散"}</td></tr>
                          <tr><td>单日最大可能损失</td><td className="mono down">¥{risk.metrics.max_loss_1d.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}</td><td className="muted">{(risk.metrics.max_loss_1d_pct * 100).toFixed(2)}% (3σ)</td></tr>
                          <tr><td>期望损失 EL</td><td className="mono down">¥{risk.metrics.expected_loss.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}</td><td className="muted">{(risk.metrics.expected_loss_pct * 100).toFixed(2)}% (PD×LGD×EAD)</td></tr>
                        </tbody>
                      </table>
                      {risk.metrics.individual_drawdowns.length > 0 && (
                        <>
                          <h4 style={{ marginTop: 10 }}>个股回撤</h4>
                          <table className="metrics-table">
                            <thead><tr><th>股票</th><th>成本</th><th>现价</th><th>回撤</th></tr></thead>
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
                      <h4>在险价值 VaR</h4>
                      <div className="stat-row">
                        <span className="stat-pill">置信水平 {(risk.var_result.confidence_level * 100).toFixed(0)}%</span>
                        <span className="stat-pill">时间跨度 {risk.var_result.time_horizon_days}天</span>
                        <span className="stat-pill">方法 {risk.var_result.method}</span>
                      </div>
                      <div className="var-display">
                        <div className="var-main">
                          <span className="var-label">VaR 绝对值</span>
                          <span className="var-value down">¥{risk.var_result.var_value.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}</span>
                        </div>
                        <div className="var-main">
                          <span className="var-label">VaR 占比</span>
                          <span className="var-value">{(risk.var_result.var_pct * 100).toFixed(2)}%</span>
                        </div>
                        <div className="var-main">
                          <span className="var-label">CVaR (Expected Shortfall)</span>
                          <span className="var-value down">¥{risk.var_result.cvar_value.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}</span>
                        </div>
                        <div className="var-main">
                          <span className="var-label">CVaR 占比</span>
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
                          <thead><tr><th>股票</th><th>权重</th><th>VaR</th></tr></thead>
                          <tbody>
                            {risk.var_result.holdings_var.map((h: any, i: number) => (
                              <tr key={i}>
                                <td>{h.name}</td>
                                <td className="mono">{((h.weight ?? 0) * 100).toFixed(1)}%</td>
                                <td className="mono down">¥{(h.var_value ?? 0).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}</td>
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
                      <h4>AI 深度分析</h4>
                      <p><strong>市场环境：</strong>{risk.llm_analysis.market_assessment}</p>
                      <p><strong>相关性风险：</strong>{risk.llm_analysis.correlation_analysis}</p>
                      <p><strong>风险综述：</strong>{risk.llm_analysis.risk_narrative}</p>
                      {risk.llm_analysis.scenario_analysis.length > 0 && (
                        <>
                          <span className="field-label">风险情景</span>
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
  try {
    if (card.type === "research" && card.data && "composite_score" in card.data) {
      const d = card.data as unknown as ResearchReport;
      return (
        <div className="card">
          <h4>投研报告 · {d.name} ({d.symbol})</h4>
          <div className="stat-row">
            <span className="stat-pill">评分 {d.composite_score}/10</span>
            <span className="stat-pill">倾向 {d.bias}</span>
          </div>
          <p>{d.summary}</p>
        </div>
      );
    }
    if (card.type === "risk" && card.data && "portfolio_summary" in card.data) {
      const d = card.data as unknown as RiskCheckup;
      return (
        <div className="card">
          <h4>风控体检</h4>
          <p>{d.portfolio_summary}</p>
          {d.alerts?.slice(0, 3).map((a, i) => (
            <p key={i} className={`alert-${a.severity}`}>{a.human_message}</p>
          ))}
          {d.llm_analysis && <p><strong>AI 分析：</strong>{d.llm_analysis.risk_narrative}</p>}
        </div>
      );
    }
    if (card.type === "news" && card.data && "items" in card.data) {
      const items = (card.data as { items: NewsItem[] }).items || [];
      return (
        <div className="card">
          <h4>相关快讯</h4>
          {items.slice(0, 3).map((n, i) => <p key={i}>{n.title} — {n.summary}</p>)}
        </div>
      );
    }
    if (card.type === "debate" && card.data && "positions" in card.data) {
      const d = card.data as { positions: { agent: string; stance: string; arguments: string }[]; vote_tally: Record<string, number>; final_bias: string; synthesis: string; symbol: string; name: string };
      const biasLabel: Record<string, string> = { bullish: "偏多", bearish: "偏空", neutral: "中性" };
      const stanceColor: Record<string, string> = { "看多": "up", "看空": "down", "中性": "" };
      return (
        <div className="card">
          <h4>多Agent辩论 · {d.name}({d.symbol})</h4>
          <div className="stat-row">
            <span className="stat-pill">看多 {d.vote_tally["看多"] || 0}</span>
            <span className="stat-pill">看空 {d.vote_tally["看空"] || 0}</span>
            <span className="stat-pill">中性 {d.vote_tally["中性"] || 0}</span>
            <span className={`stat-pill ${d.final_bias === "bullish" ? "up" : d.final_bias === "bearish" ? "down" : ""}`}>综合 {biasLabel[d.final_bias] || d.final_bias}</span>
          </div>
          {d.positions.map((p, i) => (
            <div key={i} className={`debate-position ${stanceColor[p.stance] || ""}`}>
              <strong>{p.agent}分析师</strong> <span className={`stat-pill ${stanceColor[p.stance]}`}>{p.stance}</span>
              <p className="muted" style={{ marginTop: 2 }}>{p.arguments.slice(0, 200)}{p.arguments.length > 200 ? "..." : ""}</p>
            </div>
          ))}
          {d.synthesis && (
            <div style={{ marginTop: 8, borderTop: "1px solid var(--bbg-border)", paddingTop: 8 }}>
              <strong>裁判综合</strong>
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
          <h4>财报比率 · {d.name}({d.symbol})</h4>
          <table className="metrics-table">
            <thead><tr><th>指标</th><th>当前值</th><th>行业参考</th><th>评价</th></tr></thead>
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
            <h4>研究计划</h4>
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
            <h4>步骤 {d.step_id}</h4>
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
    return <div className="card"><p>卡片数据解析失败</p></div>;
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
