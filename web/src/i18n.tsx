import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  applyLocale,
  loadLocale,
  saveLocale,
  type AppLocale,
} from "./localeSettings";

interface Dict {
  [key: string]: string | Dict;
}

const zh: Dict = {
  brand: { tagline: "AI 投研终端" },
  nav: { aria: "功能导航", chat: "对话", news: "新闻", portfolio: "持仓", risk: "风控" },
  header: {
    about: "关于",
    aboutTitle: "关于作者与参考项目",
    settings: "设置",
    settingsTitle: "大模型 API Key / 模型 / 温度",
  },
  page: {
    chat: "智能对话",
    news: "新闻快讯",
    portfolio: "持仓管理",
    risk: "风控体检",
  },
  chat: {
    chooseDepth: "请选择分析深度",
    forQuery: "针对",
    simple: "简单分析",
    complex: "复杂分析",
    choiceHint: "简单：快速直接回答；复杂：Multi-Agent 投研、多空辩论或规划执行",
    processTitle: "Multi-Agent 思考过程",
    processLive: "Multi-Agent 思考过程（进行中）",
    conclusion: "综合结论",
    placeholder: "输入消息，如：帮我分析一下贵州茅台",
    sending: "分析中...",
    send: "发送",
    disclaimer: "以上内容由 AI 生成，仅供参考，不构成投资建议。",
    connecting: "正在连接…",
    streamFailed: "流式连接失败，切换同步模式…",
    analysisDone: "分析完成",
    selectedMode: "已选择：{mode}，正在分析…",
  },
  news: { refresh: "刷新快讯", loading: "加载中...", related: "与你相关" },
  portfolio: {
    symbol: "代码/名称",
    symbolPh: "如 600519 或 贵州茅台",
    cost: "成本价",
    lots: "手数",
    buyDate: "买入日期",
    buyDateTitle: "须为 A 股交易日（有开盘的日期）",
    add: "添加",
    querying: "查询中...",
    pickStock: "请选择股票",
    quotesUpdating: "行情更新中…",
    trading: "盘中 · 显示现价（每 30 秒刷新）",
    closed: "已收盘 · 显示收盘价",
    refresh: "刷新",
    empty: "暂无持仓，请在上方添加",
    stock: "股票",
    price: "价格",
    change: "涨跌",
    costCol: "成本",
    qty: "数量",
    pnl: "盈亏",
    annualized: "年化",
    invalidCost: "请输入有效的成本价",
  },
  risk: {
    run: "持仓体检",
    running: "体检中...",
    metrics: "风险指标",
    sharpe: "夏普比率",
    sortino: "索提诺比率",
    calmar: "Calmar 比率",
    infoRatio: "信息比率",
    maxDrawdown: "最大回撤",
    volatility: "年化波动率",
    concentration: "行业集中度",
    maxLoss1d: "单日最大可能损失",
    expectedLoss: "期望损失 EL",
    stockDrawdown: "个股回撤",
    stock: "股票",
    current: "现价",
    drawdown: "回撤",
    var: "在险价值 VaR",
    confidence: "置信水平",
    horizon: "时间跨度",
    days: "天",
    method: "方法",
    varAbs: "VaR 绝对值",
    varPct: "VaR 占比",
    cvar: "CVaR (Expected Shortfall)",
    cvarPct: "CVaR 占比",
    weight: "权重",
    aiAnalysis: "AI 深度分析",
    market: "市场环境",
    correlation: "相关性风险",
    narrative: "风险综述",
    scenarios: "风险情景",
  },
  rating: {
    excellent: "优",
    good: "良",
    fair: "中",
    poor: "差",
    high: "高",
    medium: "中",
    low: "低",
    highRisk: "高危",
    watch: "关注",
    ok: "可控",
    elevated: "偏高",
    diversified: "分散",
  },
  card: {
    research: "投研报告",
    score: "评分",
    bias: "倾向",
    riskCheckup: "风控体检",
    aiBrief: "AI 分析",
    relatedNews: "相关快讯",
    debate: "多Agent辩论",
    bullish: "偏多",
    bearish: "偏空",
    neutral: "中性",
    long: "看多",
    short: "看空",
    analyst: "分析师",
    judge: "裁判综合",
    financial: "财报比率",
    metric: "指标",
    value: "当前值",
    benchmark: "行业参考",
    assessment: "评价",
    plan: "研究计划",
    step: "步骤",
    parseError: "卡片数据解析失败",
  },
  analysis: {
    simple: "简单分析",
    complex: "复杂分析（Multi-Agent）",
  },
  settings: {
    title: "设置",
    welcome: "欢迎使用 StockResearch",
    close: "关闭",
    requiredBanner:
      "请先配置大模型。API Key 仅保存在您本机浏览器，不会上传到 Cloudflare 或服务器仓库。",
    appearance: "外观风格",
    appearanceHint: "切换后立即生效，保存在本机浏览器。",
    language: "界面语言",
    languageHint: "切换后立即生效，保存在本机浏览器。",
    langZh: "中文",
    langEn: "English",
    llm: "大模型",
    llmHint:
      "API Key 保存在本机浏览器，每次请求会带给服务端用于调用大模型，不会写入数据库。保存前会先测试连接，不通则无法保存。",
    apiKey: "API Key",
    baseUrl: "API URL（文档 Base URL 或完整地址均可）",
    model: "模型 ID",
    temperature: "温度",
    tempHint: "（0 更稳定，2 更发散）",
    useMock: "使用 Mock 回复（无需 API Key，用于演示）",
    serverMock: "服务端当前启用了 USE_MOCK_LLM；勾选 Mock 可本地演示。",
    cancel: "取消",
    testing: "测试中…",
    test: "测试连接",
    saving: "保存中…",
    saveEnter: "保存并进入",
    save: "保存",
    themeOrange: "橙黑",
    themeOrangeHint: "Bloomberg 终端 · 橙顶黑底",
    themeWine: "酒红白",
    themeWineHint: "白底主界面 · 酒红强调",
    analysis: "分析模式",
    analysisHint: "股票/市场相关问题默认进行多维投研；开关控制是否追加多空辩论。",
    enableDebate: "开启多空辩论",
    debateOnNote: "开启：股票或市场走势相关问题 → 多维分析 + 多空辩论。",
    debateOffNote: "关闭：股票或市场走势相关问题 → 仅多维分析（基本面/技术面/情绪面/筹码面），不进入辩论。",
  },
  about: {
    title: "关于",
    author: "作者",
    email: "邮箱",
    xiaohongshu: "小红书",
    refs: "参考开源项目",
    disclaimer: "本产品所有 AI 输出仅供学习参考，不构成投资建议。",
    tagline: "AI 投研终端 · A 股 Multi-Agent",
  },
  stream: {
    typing: "输出中…",
    analyzing: "分析中…",
    waiting: "等待 Agent 输出…",
    round: "第 {n} 轮",
    long: "看多",
    short: "看空",
    aggressive: "激进",
    neutral: "中性",
    conservative: "审慎",
    vote: "Battle 投票",
    voteBody: "偏多 {bull} · 偏空 {bear} · 中性 {neutral}{leading}",
    leading: " · 领先 {value}",
    judge: "裁判结论",
    overallRisk: "整体风险",
    portfolioBias: "组合倾向",
    process: "分析过程",
    perStock: "逐股建议（共 {n} 只）",
    priority: "优先级",
    portfolioConclusion: "组合结论",
    divergence: "分歧",
  },
};

const en: Dict = {
  brand: { tagline: "AI Research Terminal" },
  nav: { aria: "Navigation", chat: "Chat", news: "News", portfolio: "Portfolio", risk: "Risk" },
  header: {
    about: "About",
    aboutTitle: "About the author & references",
    settings: "Settings",
    settingsTitle: "LLM API Key / model / temperature",
  },
  page: {
    chat: "Smart Chat",
    news: "News Feed",
    portfolio: "Holdings",
    risk: "Risk Checkup",
  },
  chat: {
    chooseDepth: "Choose analysis depth",
    forQuery: "For",
    simple: "Quick",
    complex: "Deep dive",
    choiceHint: "Quick: direct answer; Deep: Multi-Agent research, debate, or planning",
    processTitle: "Multi-Agent reasoning",
    processLive: "Multi-Agent reasoning (in progress)",
    conclusion: "Conclusion",
    placeholder: "Ask anything, e.g. analyze Kweichow Moutai",
    sending: "Analyzing...",
    send: "Send",
    disclaimer: "AI-generated content for reference only; not investment advice.",
    connecting: "Connecting…",
    streamFailed: "Stream failed, falling back to sync mode…",
    analysisDone: "Analysis complete",
    selectedMode: "Selected: {mode}, analyzing…",
  },
  news: { refresh: "Refresh feed", loading: "Loading...", related: "Relevant to you" },
  portfolio: {
    symbol: "Symbol / name",
    symbolPh: "e.g. 600519 or Moutai",
    cost: "Cost",
    lots: "Lots",
    buyDate: "Buy date",
    buyDateTitle: "Must be an A-share trading day",
    add: "Add",
    querying: "Looking up...",
    pickStock: "Select a stock",
    quotesUpdating: "Updating quotes…",
    trading: "Market open · live price (refreshes every 30s)",
    closed: "Market closed · closing price",
    refresh: "Refresh",
    empty: "No holdings yet — add one above",
    stock: "Stock",
    price: "Price",
    change: "Chg%",
    costCol: "Cost",
    qty: "Qty",
    pnl: "P&L",
    annualized: "Ann.",
    invalidCost: "Enter a valid cost price",
  },
  risk: {
    run: "Run checkup",
    running: "Checking...",
    metrics: "Risk metrics",
    sharpe: "Sharpe ratio",
    sortino: "Sortino ratio",
    calmar: "Calmar ratio",
    infoRatio: "Information ratio",
    maxDrawdown: "Max drawdown",
    volatility: "Annualized vol.",
    concentration: "Sector concentration",
    maxLoss1d: "Max 1-day loss",
    expectedLoss: "Expected loss (EL)",
    stockDrawdown: "Stock drawdowns",
    stock: "Stock",
    current: "Last",
    drawdown: "Drawdown",
    var: "Value at Risk (VaR)",
    confidence: "Confidence",
    horizon: "Horizon",
    days: "days",
    method: "Method",
    varAbs: "VaR (absolute)",
    varPct: "VaR (%)",
    cvar: "CVaR (Expected Shortfall)",
    cvarPct: "CVaR (%)",
    weight: "Weight",
    aiAnalysis: "AI deep dive",
    market: "Market view",
    correlation: "Correlation risk",
    narrative: "Risk narrative",
    scenarios: "Risk scenarios",
  },
  rating: {
    excellent: "Excellent",
    good: "Good",
    fair: "Fair",
    poor: "Poor",
    high: "High",
    medium: "Medium",
    low: "Low",
    highRisk: "High risk",
    watch: "Watch",
    ok: "OK",
    elevated: "Elevated",
    diversified: "Diversified",
  },
  card: {
    research: "Research report",
    score: "Score",
    bias: "Bias",
    riskCheckup: "Risk checkup",
    aiBrief: "AI summary",
    relatedNews: "Related news",
    debate: "Multi-agent debate",
    bullish: "Bullish",
    bearish: "Bearish",
    neutral: "Neutral",
    long: "Long",
    short: "Short",
    analyst: "analyst",
    judge: "Judge synthesis",
    financial: "Financial ratios",
    metric: "Metric",
    value: "Value",
    benchmark: "Benchmark",
    assessment: "View",
    plan: "Research plan",
    step: "Step",
    parseError: "Failed to parse card data",
  },
  analysis: {
    simple: "Quick analysis",
    complex: "Deep analysis (Multi-Agent)",
  },
  settings: {
    title: "Settings",
    welcome: "Welcome to StockResearch",
    close: "Close",
    requiredBanner:
      "Configure an LLM first. Your API key stays in this browser only — never uploaded to Cloudflare or the server repo.",
    appearance: "Appearance",
    appearanceHint: "Applies immediately and is saved in this browser.",
    language: "Language",
    languageHint: "Applies immediately and is saved in this browser.",
    langZh: "中文",
    langEn: "English",
    llm: "Language model",
    llmHint:
      "API key is stored in this browser and sent with each request for LLM calls — not saved server-side. Connection is tested before save.",
    apiKey: "API Key",
    baseUrl: "API URL (full endpoint, used as-is)",
    model: "Model ID",
    temperature: "Temperature",
    tempHint: "(0 = stable, 2 = creative)",
    useMock: "Use mock replies (no API key, for demo)",
    serverMock: "Server has USE_MOCK_LLM enabled; check Mock for local demo.",
    cancel: "Cancel",
    testing: "Testing…",
    test: "Test connection",
    saving: "Saving…",
    saveEnter: "Save & continue",
    save: "Save",
    themeOrange: "Orange / black",
    themeOrangeHint: "Bloomberg terminal · orange header",
    themeWine: "Wine / white",
    themeWineHint: "Light UI · wine accents",
    analysis: "Analysis",
    analysisHint:
      "Stock/market questions use multi-dimensional research by default; toggle adds bull/bear debate.",
    enableDebate: "Enable bull/bear debate",
    debateOnNote: "On: stock or market questions → multi-dim analysis + debate.",
    debateOffNote: "Off: stock or market questions → multi-dim analysis only (no debate).",
  },
  about: {
    title: "About",
    author: "Author",
    email: "Email",
    xiaohongshu: "Xiaohongshu",
    refs: "Open-source references",
    disclaimer: "All AI output is for learning only — not investment advice.",
    tagline: "AI research terminal · A-share Multi-Agent",
  },
  stream: {
    typing: "Streaming…",
    analyzing: "Analyzing…",
    waiting: "Waiting for agent output…",
    round: "Round {n}",
    long: "Long",
    short: "Short",
    aggressive: "Aggressive",
    neutral: "Neutral",
    conservative: "Conservative",
    vote: "Battle vote",
    voteBody: "Bull {bull} · Bear {bear} · Neutral {neutral}{leading}",
    leading: " · Leading {value}",
    judge: "Judge verdict",
    overallRisk: "Overall risk",
    portfolioBias: "Portfolio bias",
    process: "Analysis process",
    perStock: "Per-stock actions ({n})",
    priority: "Priority",
    portfolioConclusion: "Portfolio conclusion",
    divergence: "Divergence",
  },
};

const dictionaries: Record<AppLocale, Dict> = { zh, en };

function resolve(dict: Dict, path: string): string | undefined {
  const parts = path.split(".");
  let cur: string | Dict | undefined = dict;
  for (const part of parts) {
    if (cur == null || typeof cur === "string") return undefined;
    cur = cur[part];
  }
  return typeof cur === "string" ? cur : undefined;
}

export type TParams = Record<string, string | number>;

export function createT(locale: AppLocale) {
  const dict = dictionaries[locale];
  return (key: string, params?: TParams): string => {
    let text = resolve(dict, key) ?? resolve(dictionaries.zh, key) ?? key;
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        text = text.split(`{${k}}`).join(String(v));
      }
    }
    return text;
  };
}

interface I18nContextValue {
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
  t: (key: string, params?: TParams) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<AppLocale>(loadLocale);

  const setLocale = useCallback((next: AppLocale) => {
    setLocaleState(next);
    saveLocale(next);
    applyLocale(next);
  }, []);

  const value = useMemo(
    () => ({ locale, setLocale, t: createT(locale) }),
    [locale, setLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
