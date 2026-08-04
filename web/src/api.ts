import {
  chatBodyField,
  loadModeSettings,
  type AnalysisDepth,
  type ModeSettingsApiPayload,
} from "./modeSettings";
import { dataSourceRequestHeaders } from "./dataSourceSettings";
import {
  llmBodyField,
  llmFormToApiBody,
  llmRequestHeaders,
  type LlmSettingsMeta,
  type LlmTestResult,
  type LlmUserSettings,
} from "./llmSettings";
import { createJsonSseStream } from "./apiSse";

export type { LlmSettingsMeta };

/** Build-time optional origin, e.g. https://api.example.com (no trailing slash). */
const API_ORIGIN =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const API = API_ORIGIN ? `${API_ORIGIN}/api/v1` : "/api/v1";

function apiUrl(path: string): string {
  return `${API}${path}`;
}

function formatApiDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) =>
        typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item),
      )
      .join("; ");
  }
  return "";
}

const DEFAULT_TIMEOUT_MS = 30_000;
const RETRY_COUNT = 2;
const RETRY_DELAY_MS = 1000;

async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(id);
  }
}

async function fetchWithRetry(
  url: string,
  options: RequestInit,
  retries = RETRY_COUNT,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  // Only idempotent methods are safe to retry — retrying a POST/PUT/DELETE
  // that already reached the server could duplicate writes (holdings, trades).
  const method = (options.method ?? "GET").toUpperCase();
  const idempotent = method === "GET" || method === "HEAD" || method === "OPTIONS";
  const maxAttempts = idempotent ? retries : 0;
  let lastError: Error | null = null;
  for (let attempt = 0; attempt <= maxAttempts; attempt++) {
    try {
      const resp = await fetchWithTimeout(url, options, timeoutMs);
      if (resp.status >= 500 && attempt < maxAttempts) {
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS * (attempt + 1)));
        continue;
      }
      return resp;
    } catch (err) {
      lastError = err as Error;
      if (attempt < maxAttempts) {
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS * (attempt + 1)));
      }
    }
  }
  throw lastError;
}

async function requestPlain<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const resp = await fetchWithRetry(`${API}${path}`, { ...options, headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(formatApiDetail(err.detail) || "请求失败");
  }
  return resp.json();
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...dataSourceRequestHeaders(),
    ...(options.headers as Record<string, string>),
  };

  const resp = await fetchWithRetry(`${API}${path}`, { ...options, headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(formatApiDetail(err.detail) || "请求失败");
  }
  return resp.json();
}

/** Like request() but also sends LLM credentials — use only for LLM-dependent endpoints. */
async function requestWithLlm<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs?: number,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...llmRequestHeaders(),
    ...dataSourceRequestHeaders(),
    ...(options.headers as Record<string, string>),
  };

  const resp = await fetchWithRetry(
    `${API}${path}`,
    { ...options, headers },
    RETRY_COUNT,
    timeoutMs,
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(formatApiDetail(err.detail) || "请求失败");
  }
  return resp.json();
}

export interface AgentStreamEvent {
  type: string;
  [key: string]: unknown;
  message?: string;
  message_key?: string;
  message_params?: Record<string, string | number | boolean>;
  stream_id?: string;
  delta?: string;
  agent_id?: string;
  agent_name?: string;
  role?: string;
  content?: string;
  round?: number;
  bull?: string;
  bear?: string;
  aggressive?: string;
  neutral_view?: string;
  conservative?: string;
  vote?: string;
  bullish?: number;
  bearish?: number;
  neutral?: number;
  leading?: string;
  verdict?: string;
  summary?: string;
  reason?: string;
  divergence?: string;
  risk_level?: string;
  position_action?: string;
  analysis_process?: string;
  holding_actions?: HoldingAction[];
  response?: ChatResponse;
  result?: Record<string, unknown>;
  candidates?: { symbol: string; name: string }[];
  original_message?: string;
  // News deep analysis events
  symbol?: string;
  name?: string;
  assessment?: string;
  direction?: string;
  key_points?: string[];
}

export interface HoldingAction {
  symbol: string;
  name: string;
  action: string;
  reason: string;
  priority?: string;
}

export type ExecutionPreference = "react" | "plan_execute" | "preset" | "auto";

export interface ChatUserContextPayload {
  kind: "focus" | "risk" | "news" | "stock" | "report";
  label: string;
  detail?: string;
  symbol?: string;
  metadata?: Record<string, string>;
}

export interface ChatStreamOptions {
  confirmedSymbol?: string;
  confirmedName?: string;
  executionPreference?: ExecutionPreference;
  userContext?: ChatUserContextPayload | null;
}

export const api = {
  modeSettings: () => request<ModeSettingsApiPayload>("/settings/mode"),
  saveModeSettings: (payload: ModeSettingsApiPayload) =>
    request<ModeSettingsApiPayload>("/settings/mode", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  llmSettings: () => request<LlmSettingsMeta>("/settings/llm"),
  saveLlmSettings: (form: LlmUserSettings) =>
    requestWithLlm<LlmSettingsMeta>("/settings/llm", {
      method: "PUT",
      body: JSON.stringify(llmFormToApiBody(form)),
    }),
  testLlmConnection: (form: LlmUserSettings) =>
    requestPlain<LlmTestResult>("/settings/llm/test", {
      method: "POST",
      body: JSON.stringify(llmFormToApiBody(form)),
    }),
  chat: (message: string, sessionId?: string, options?: ChatStreamOptions) =>
    requestWithLlm<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        session_id: sessionId,
        user_context: options?.userContext ?? undefined,
        confirmed_symbol: options?.confirmedSymbol,
        confirmed_name: options?.confirmedName,
        execution_preference: options?.executionPreference,
        ...chatBodyField(),
        ...llmBodyField(),
      }),
    }),
  chatStream: (
    message: string,
    sessionId?: string,
    onEvent?: (event: AgentStreamEvent) => void,
    options?: ChatStreamOptions,
    signal?: AbortSignal,
  ) =>
    createJsonSseStream<ChatResponse, AgentStreamEvent>({
      url: apiUrl("/chat/stream"),
      method: "POST",
      headers: llmRequestHeaders(),
      body: {
        message,
        session_id: sessionId,
        user_context: options?.userContext ?? undefined,
        confirmed_symbol: options?.confirmedSymbol,
        confirmed_name: options?.confirmedName,
        execution_preference: options?.executionPreference,
        ...chatBodyField(),
        ...llmBodyField(),
      },
      onEvent,
      signal,
      extractResult: (event) =>
        event.type === "done" && event.response ? (event.response as ChatResponse) : undefined,
    }),
  holdings: () => request<Holding[]>("/portfolio/holdings"),
  allocationDeviation: (targets: Record<string, number>) =>
    request<AllocationDeviation>("/portfolio/allocation/deviation", {
      method: "POST",
      body: JSON.stringify({ targets }),
    }),
  holdingsEnriched: (opts?: { forceRefresh?: boolean }) => {
    const qs = opts?.forceRefresh ? "?force_refresh=true" : "";
    return request<HoldingEnriched[]>(`/portfolio/holdings/enriched${qs}`);
  },
  addHolding: (h: HoldingCreatePayload) =>
    request("/portfolio/holdings", { method: "POST", body: JSON.stringify(h) }),
  deleteHolding: (id: number) => request(`/portfolio/holdings/${id}`, { method: "DELETE" }),
  applyHoldingTransactions: (payload: HoldingTransactionBatchPayload) =>
    request<HoldingTransactionResult>("/portfolio/holdings/transactions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  portfolioTrades: (limit = 30) => request<TradeRecord[]>(`/portfolio/trades?limit=${limit}`),
  portfolioPerformance: (days = 90) =>
    request<PortfolioPerformance>(`/portfolio/performance?days=${days}`),
  portfolioEvents: (days = 45) => request<PortfolioEvents>(`/portfolio/events?days=${days}`),
  portfolioScreen: (payload: ScreenRequest) =>
    request<ScreenResult>("/portfolio/screen", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  lookupStock: (query: string) =>
    request<StockLookupOut>("/portfolio/holdings/lookup", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),
  newsFeed: () => request<NewsItem[]>("/news/feed"),
  newsSectors: () => request<SectorPreferences>("/news/sectors"),
  updateNewsSectors: (sectors: string[]) =>
    request<SectorPreferences>("/news/sectors", {
      method: "PUT",
      body: JSON.stringify({ sectors }),
    }),
  ingestNews: async () => {
    const accepted = await request<NewsIngestAccepted>("/news/ingest?limit=10", { method: "POST" });
    return waitForNewsIngestJob(accepted.job_id);
  },
  newsIngestJob: (jobId: string) =>
    request<NewsIngestJob>(`/news/ingest/${encodeURIComponent(jobId)}`),
  research: (symbol: string, analysisDepth?: AnalysisDepth) => {
    const depth = analysisDepth ?? loadModeSettings().analysisDepth;
    const params = new URLSearchParams({ symbol, analysis_depth: depth });
    return request<ResearchReport>(`/research/analyze?${params.toString()}`);
  },
  researchStream: (
    symbol: string,
    onEvent?: (event: AgentStreamEvent) => void,
    analysisDepth?: AnalysisDepth,
  ) => {
    const depth = analysisDepth ?? loadModeSettings().analysisDepth;
    const params = new URLSearchParams({ symbol, analysis_depth: depth });
    return createJsonSseStream<ResearchReport, AgentStreamEvent>({
      url: apiUrl(`/research/analyze/stream?${params.toString()}`),
      headers: llmRequestHeaders(),
      onEvent,
      extractResult: (event) =>
        event.type === "done" && event.result
          ? (event.result as unknown as ResearchReport)
          : undefined,
    });
  },
  riskCheckup: () =>
    requestWithLlm<RiskCheckup>(
      "/risk/checkup",
      {
        method: "POST",
        body: JSON.stringify({ ...chatBodyField() }),
      },
      120_000,
    ),
  riskCheckupStream: (onEvent?: (event: AgentStreamEvent) => void, signal?: AbortSignal) =>
    createJsonSseStream<RiskCheckup, AgentStreamEvent>({
      url: apiUrl("/risk/checkup/stream"),
      method: "POST",
      headers: llmRequestHeaders(),
      body: { ...chatBodyField() },
      signal,
      timeoutMs: 120_000,
      onEvent,
      extractResult: (event) =>
        event.type === "done" && event.result
          ? (event.result as unknown as RiskCheckup)
          : undefined,
    }),
  advisorAllocation: (
    riskTolerance: "conservative" | "moderate" | "aggressive",
    monthlyIncome?: number,
  ) =>
    requestWithLlm<AssetAllocation>(
      "/advisor/allocation",
      {
        method: "POST",
        body: JSON.stringify({
          risk_tolerance: riskTolerance,
          monthly_income: monthlyIncome,
          ...chatBodyField(),
        }),
      },
      60_000,
    ),
  marketOverview: () => request<MarketOverview>("/market/overview"),
  stockQuotes: (symbols: string, opts?: { forceRefresh?: boolean }) => {
    const params = new URLSearchParams({ symbols });
    if (opts?.forceRefresh) params.set("force_refresh", "true");
    return request<StockQuoteOut[]>(`/market/quotes?${params.toString()}`);
  },
  dataSourceStatus: () => request<DataSourceStatus>("/market/data-status"),
  klineChart: (symbol: string, days = 90, before?: string) => {
    const params = new URLSearchParams({ symbol, days: String(days) });
    if (before) params.set("before", before);
    return request<KlineChart>(`/market/kline?${params.toString()}`);
  },
  chartOverlays: (symbol: string) =>
    request<ChartOverlaySet>(`/market/overlays?symbol=${encodeURIComponent(symbol)}`),
  listReports: () => request<ResearchReportListItem[]>("/research/reports"),
  downloadReportMarkdown: (id: number) => {
    window.open(apiUrl(`/research/reports/${id}/markdown`), "_blank", "noopener,noreferrer");
  },
  downloadReportPdf: (id: number) => {
    window.open(apiUrl(`/research/reports/${id}/pdf`), "_blank", "noopener,noreferrer");
  },
  /** Download formal report from in-memory card payload (Markdown). */
  exportReportMarkdown: async (report: ResearchReport) => {
    await downloadReportBlob("/research/export/markdown", report, `${report.symbol}-report.md`);
  },
  /** Download formal report from in-memory card payload (PDF). */
  exportReportPdf: async (report: ResearchReport) => {
    await downloadReportBlob("/research/export/pdf", report, `${report.symbol}-report.pdf`);
  },
  exportReportJson: async (report: ResearchReport) => {
    await downloadReportBlob("/research/export/json", report, `${report.symbol}-report.json`);
  },
  exportReportCsv: async (report: ResearchReport) => {
    await downloadReportBlob("/research/export/csv", report, `${report.symbol}-factors.csv`);
  },
  signalBacktest: () => request<SignalBacktest>("/research/signal-backtest"),
  researchTimeline: (symbol: string, includePostHoc = true) =>
    request<ResearchTimeline>(
      `/research/timeline?symbol=${encodeURIComponent(symbol)}&include_post_hoc=${includePostHoc}`,
    ),
  reportPostHoc: (id: number) => request<ReportPostHoc>(`/research/reports/${id}/post-hoc`),
  compareSymbols: (symbols: string[]) =>
    request<CompareTable>("/research/compare", {
      method: "POST",
      body: JSON.stringify({ symbols }),
    }),
  eventStudy: (symbol: string, eventFilter: "earnings" | "risk" | "all" = "earnings") =>
    request<EventStudy>(
      `/research/event-study?symbol=${encodeURIComponent(symbol)}&event_filter=${eventFilter}`,
    ),
  eventStudyBatch: (symbols: string[], eventFilter: "earnings" | "risk" | "all" = "earnings") =>
    request<EventStudyBatch>("/research/event-study/batch", {
      method: "POST",
      body: JSON.stringify({ symbols, event_filter: eventFilter }),
    }),
  hypothesisPresets: () => request<Record<string, string>>("/research/hypothesis/presets"),
  hypothesisVerify: (symbol: string, rule: string, lookbackDays = 240) =>
    request<HypothesisVerify>("/research/hypothesis/verify", {
      method: "POST",
      body: JSON.stringify({ symbol, rule, lookback_days: lookbackDays }),
    }),
  batchResearch: (symbols: string[], analysisDepth?: AnalysisDepth) =>
    requestWithLlm<BatchResearch>(
      "/research/batch",
      {
        method: "POST",
        body: JSON.stringify({
          symbols,
          analysis_depth: analysisDepth ?? loadModeSettings().analysisDepth,
          with_debate: false,
        }),
      },
      300_000,
    ),
  refillResearch: (symbol: string, gaps: string[], analysisDepth?: AnalysisDepth) =>
    requestWithLlm<ResearchReport>(
      "/research/refill",
      {
        method: "POST",
        body: JSON.stringify({
          symbol,
          gaps,
          analysis_depth: analysisDepth ?? loadModeSettings().analysisDepth,
        }),
      },
      300_000,
    ),
  searchMemory: (q: string) =>
    request<MemorySearchResult>(`/research/memory/search?q=${encodeURIComponent(q)}`),
  generateBriefing: (kind: "premarket" | "intraday" | "postmarket") =>
    requestWithLlm<Briefing>(`/briefing/generate?kind=${kind}`, {
      method: "POST",
      body: JSON.stringify(chatBodyField()),
    }),
  latestBriefing: (kind: "premarket" | "intraday" | "postmarket") =>
    request<Briefing | null>(`/briefing/latest?kind=${kind}`),
  briefingHistory: (kind: "premarket" | "intraday" | "postmarket" | "all" = "all", limit = 10) =>
    request<Briefing[]>(`/briefing/history?kind=${kind}&limit=${limit}`),
  briefingSchedule: () => request<BriefingSchedule>("/briefing/schedule"),
  setBriefingSchedule: (enabled: boolean) =>
    request<BriefingSchedule>(`/briefing/schedule?enabled=${enabled}`, {
      method: "PUT",
    }),
  loadDemo: () =>
    request<{ status: string; count: number; demo: boolean }>("/portfolio/demo", {
      method: "POST",
    }),
  clearDemo: () =>
    request<{ status: string; deleted: number }>("/portfolio/demo", {
      method: "DELETE",
    }),
  demoStatus: () => request<{ demo: boolean }>("/portfolio/demo/status"),
  dailyActions: () => request<DailyActionCenter>("/action-center/daily"),
  watchlist: () => request<WatchlistItem[]>("/portfolio/watchlist"),
  addWatchlist: (payload: { symbol: string; name: string }) =>
    request<WatchlistItem>("/portfolio/watchlist", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteWatchlist: (id: number) => request(`/portfolio/watchlist/${id}`, { method: "DELETE" }),
  sectorMovers: (limit = 8) => request<SectorMovers>(`/market/sectors?limit=${limit}`),
  sectorBoardsAll: () => request<SectorBoardsAll>(`/market/sectors?all=true`),
  indexIntraday: (symbols: string[]) =>
    request<IndexIntraday[]>(`/market/intraday?symbols=${symbols.join(",")}`),
  priceAlertSettings: () => request<PriceAlertSettings>("/alerts/settings"),
  updatePriceAlertSettings: (payload: Partial<PriceAlertSettings>) =>
    request<PriceAlertSettings>("/alerts/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  priceAlertNotifications: (unreadOnly = false) =>
    request<PriceAlertNotification[]>(`/alerts/notifications?unread_only=${unreadOnly}`),
  markPriceAlertRead: (id: number) =>
    request(`/alerts/notifications/${id}/read`, { method: "POST" }),
  markAllPriceAlertsRead: () =>
    request<{ updated: number }>("/alerts/notifications/read-all", {
      method: "POST",
    }),
  analyzeNews: (
    newsId: number,
    symbol: string,
    onEvent?: (event: AgentStreamEvent) => void,
    signal?: AbortSignal,
  ) =>
    createJsonSseStream<NewsAnalysis, AgentStreamEvent>({
      url: apiUrl(`/news/${newsId}/analyze/stream?symbol=${encodeURIComponent(symbol)}`),
      headers: llmRequestHeaders(),
      signal,
      onEvent,
      extractResult: (event) =>
        event.type === "done" && event.result
          ? (event.result as unknown as NewsAnalysis)
          : undefined,
    }),
  glossary: () => requestPlain<GlossaryTerm[]>("/glossary"),
  marketSentiment: () => request<SentimentData>("/market/sentiment"),
  sectorSentiment: (name: string) =>
    request<SentimentData>(`/market/sector-sentiment?name=${encodeURIComponent(name)}`),
  stockSentiment: (symbol: string, name?: string) =>
    request<SentimentData>(
      `/market/stock-sentiment?symbol=${encodeURIComponent(symbol)}&name=${encodeURIComponent(name ?? "")}`,
    ),
};

/** 词库条目，供投顾模式 TermPopover 渲染可点击弹窗。 */
export interface GlossaryTerm {
  id: string;
  short: string;
  en: string;
  def: string;
  analogy: string;
  custom?: boolean;
}

export interface LlmUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  model?: string | null;
  estimated_cost_cny?: number | null;
  is_estimate?: boolean;
  llm_calls?: number;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  cards: Card[];
  intent: string;
  disclaimer: string;
  follow_up_questions?: string[];
  llm_usage?: LlmUsage | null;
}

export interface StockChoiceCardData {
  message: string;
  status: string;
  candidates: { symbol: string; name: string }[];
  original_message: string;
}

export interface RouteChoiceOption {
  id: ExecutionPreference;
  label?: string;
  description?: string;
  label_key?: string;
  description_key?: string;
  label_params?: Record<string, string | number>;
  description_params?: Record<string, string | number>;
}

export interface RouteChoiceCardData {
  message?: string;
  reason_key?: string;
  reason_params?: Record<string, string | number>;
  original_message: string;
  finance_related: boolean;
  preset_mode: string | null;
  options: RouteChoiceOption[];
}

export interface Card {
  type:
    | "news"
    | "research"
    | "risk"
    | "text"
    | "market"
    | "debate"
    | "plan"
    | "financial"
    | "stock_choice"
    | "route_choice"
    | "chart_overlays";
  data: Record<string, unknown>;
}

export interface HoldingEnriched extends Holding {
  price?: number | null;
  change_pct?: number | null;
  open?: number | null;
  price_label: string;
  market_session: "trading" | "closed";
  profit_amount?: number | null;
  profit_pct?: number | null;
  annualized_pct?: number | null;
  quote_available: boolean;
}

export interface Holding {
  id?: number;
  symbol: string;
  name: string;
  cost_price: number;
  quantity: number;
  sector: string;
  buy_date?: string | null;
}

export interface HoldingCreatePayload {
  query?: string;
  symbol?: string;
  name?: string;
  cost_price: number;
  lots: number;
  sector?: string;
  buy_date?: string;
}

export interface HoldingTransactionItem {
  side: "buy" | "sell";
  symbol?: string;
  name?: string;
  query?: string;
  cost_price?: number;
  lots: number;
  trade_date?: string;
  note?: string;
}

export interface TradeRecord {
  id: number;
  symbol: string;
  name: string;
  side: "buy" | "sell";
  price: number;
  quantity: number;
  trade_date: string | null;
  realized_pnl: number | null;
  note: string | null;
  created_at: string;
  report_id: number | null;
  report_date: string | null;
  report_bias: string | null;
}

export interface PerformancePoint {
  date: string;
  portfolio_index: number;
  benchmark_index: number;
}

export interface PortfolioPerformance {
  days: number;
  benchmark_symbol: string;
  benchmark_name: string;
  series: PerformancePoint[];
  portfolio_return_pct: number | null;
  benchmark_return_pct: number | null;
  realized_pnl_total: number;
  trade_count: number;
  partial: boolean;
  message: string | null;
}

export interface PortfolioEvent {
  symbol: string;
  name: string;
  kind: "earnings" | "lockup";
  event_date: string;
  detail: string | null;
  scope: "holding" | "watchlist";
}

export interface PortfolioEvents {
  events: PortfolioEvent[];
  days: number;
  period: string | null;
  partial: boolean;
  message: string | null;
}

export type ScreenFactorKey = "momentum_20d" | "volatility_20d" | "pe_percentile";

export interface ScreenCondition {
  key: ScreenFactorKey;
  op: "<=" | "<" | ">=" | ">";
  value: number;
}

export interface ScreenRequest {
  universe: "holdings" | "watchlist" | "all";
  conditions: ScreenCondition[];
}

export interface ScreenHit {
  symbol: string;
  name: string;
  sector: string | null;
  scope: "holding" | "watchlist";
  factors: Record<string, number | null>;
}

export interface ScreenResult {
  hits: ScreenHit[];
  scanned: number;
  skipped: number;
  message: string | null;
}

export interface HoldingTransactionBatchPayload {
  transactions: HoldingTransactionItem[];
}

export interface HoldingTransactionResult {
  applied: number;
  holdings: Holding[];
}

export interface StockLookupOut {
  status: "confirmed" | "ambiguous" | "not_found";
  symbol: string | null;
  name: string | null;
  sector: string | null;
  message: string;
  candidates: { symbol: string; name: string }[];
  normalized_query: string;
}

export interface NewsItem {
  id: number;
  title: string;
  summary: string;
  source: string;
  sentiment: string;
  impact_level: string;
  related_to_user: boolean;
  entities: string[];
  category: "market" | "sector" | "holding";
  published_at: string;
}

export interface SectorPreferences {
  available: string[];
  selected: string[];
}

export interface NewsIngestAccepted {
  job_id: string;
  status: "queued";
}

export interface NewsIngestJob {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  inserted: number;
  scanned: number;
  skipped: number;
  purged: number;
  message: string;
  error?: string | null;
}

async function waitForNewsIngestJob(jobId: string, timeoutMs = 60_000): Promise<NewsIngestJob> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const job = await requestPlain<NewsIngestJob>(`/news/ingest/${encodeURIComponent(jobId)}`);
    if (job.status === "completed") return job;
    if (job.status === "failed") {
      throw new Error(job.error || job.message || "News ingest failed");
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  throw new Error("News ingest timed out");
}

export interface DimensionEvidence {
  source: string;
  date?: string | null;
  snippet: string;
  url?: string | null;
  kind?: string;
}

export interface DimensionResult {
  agent: string;
  score: number;
  confidence: string;
  highlights: string[];
  risks: string[];
  data_sources: string[];
  analysis?: string;
  evidence?: DimensionEvidence[];
  gaps?: string[];
  partial?: boolean;
}

export interface DebateRoundResult {
  round: number;
  bull_argument: string;
  bear_rebuttal: string;
}

export interface DebateResult {
  rounds: DebateRoundResult[];
  judge_verdict: string;
  consensus: string;
  core_divergence: string;
  final_bias: string;
  confidence: string;
  vote_tally?: Record<string, number> | null;
  manager_thesis?: string | null;
}

export interface AshareFactor {
  category: string;
  name: string;
  status: "verified" | "partial" | "missing";
  impact: "liquidity" | "sentiment" | "fundamental" | "valuation" | "event" | "technical";
  evidence: string[];
  missing: string[];
  source_details: {
    key: string;
    label: string;
    layer: string;
    provider: string;
    status: "verified" | "missing";
    note?: string | null;
  }[];
}

export interface MasterCommentaryItem {
  master: string;
  name: string;
  signal: "bullish" | "neutral" | "bearish";
  signal_text: string;
  confidence: number;
  reasoning: string;
  key_metric: string;
}

export interface NumericFactor {
  key: string;
  label: string;
  value?: number | null;
  percentile?: number | null;
  as_of?: string | null;
  unit?: string;
  partial?: boolean;
  note?: string | null;
  bars_source?: string | null;
  bars_adjust?: string | null;
}

export interface BarsProvenance {
  source: string;
  adjust: string;
  as_of?: string | null;
  partial?: boolean;
  note?: string | null;
}

export interface ReportPostHocHorizon {
  days: number;
  return_pct: number | null;
  partial?: boolean;
  note?: string | null;
  bars_adjust?: string | null;
  bars_source?: string | null;
}

export interface ReportPostHoc {
  report_id: number;
  symbol: string;
  horizons: ReportPostHocHorizon[];
  disclaimer?: string;
  label?: string;
  point_in_time?: boolean;
  signal_as_of?: string | null;
  pit_note?: string;
}

export interface ResearchTimelineFactorSnap {
  key: string;
  label: string;
  value?: number | null;
  percentile?: number | null;
  partial?: boolean;
}

export interface ResearchTimelineEntry {
  report_id: number;
  created_at: string;
  bias: string;
  composite_score: number;
  analysis_depth?: string;
  summary?: string;
  factor_alignment_note?: string | null;
  factors: ResearchTimelineFactorSnap[];
  post_hoc: ReportPostHocHorizon[];
  bias_changed?: boolean;
  score_delta?: number | null;
  thesis_claim?: string | null;
}

export interface ResearchTimeline {
  symbol: string;
  name: string;
  entries: ResearchTimelineEntry[];
  point_in_time?: boolean;
  notes?: string[];
  disclaimer?: string;
}

export interface CompareRow {
  symbol: string;
  name: string;
  factors: NumericFactor[];
  bars_adjust: string;
  bars_source: string;
  bars_as_of?: string | null;
  partial: boolean;
  note?: string | null;
}

export interface CompareTable {
  rows: CompareRow[];
  as_of: string;
  point_in_time?: boolean;
  notes?: string[];
}

export interface EventStudyWindow {
  days: number;
  sample_count: number;
  avg_return_pct?: number | null;
  positive_rate_pct?: number | null;
}

export interface EventStudyEvent {
  title: string;
  event_kind: string;
  event_date: string;
  returns: Record<string, number | null>;
  partial?: boolean;
  note?: string | null;
  url?: string | null;
}

export interface EventStudy {
  symbol: string;
  name: string;
  event_filter: string;
  events: EventStudyEvent[];
  windows: EventStudyWindow[];
  kind_counts?: Record<string, number>;
  bars_adjust?: string;
  notes?: string[];
  point_in_time?: boolean;
}

export interface EventStudyBatch {
  items: EventStudy[];
  event_filter: string;
  as_of?: string | null;
  notes?: string[];
  disclaimer?: string;
}

export interface HypothesisWindow {
  days: number;
  sample_count: number;
  avg_return_pct?: number | null;
  hit_rate_pct?: number | null;
}

export interface HypothesisVerify {
  symbol: string;
  name: string;
  rule: string;
  rule_label: string;
  windows: HypothesisWindow[];
  sample_count: number;
  point_in_time?: boolean;
  notes?: string[];
  partial?: boolean;
}

export interface BatchResearchItem {
  symbol: string;
  name: string;
  report?: ResearchReport | null;
  error?: string | null;
  partial?: boolean;
}

export interface BatchResearch {
  items: BatchResearchItem[];
  as_of: string;
  notes?: string[];
}

export interface ImpactPeakDayOut {
  date: string;
  idio_return_pct: number;
  event_title?: string | null;
  event_kind?: "earnings" | "risk" | "other" | null;
  event_fwd_return_5d_pct?: number | null;
  unexplained?: boolean;
}

export interface ImpactOut {
  window_trading_days: number;
  stock_return_pct?: number | null;
  market_contrib_pct?: number | null;
  industry_contrib_pct?: number | null;
  idio_return_pct?: number | null;
  model?: string;
  r_squared?: number | null;
  market_symbol?: string;
  industry_proxy?: string;
  partial?: boolean;
  gaps?: string[];
  peak_days?: ImpactPeakDayOut[];
  point_in_time?: boolean;
}

export interface PricingBridgeOut {
  window_label?: string;
  price_change_pct?: number | null;
  earnings_contrib_pct?: number | null;
  multiple_contrib_pct?: number | null;
  pe_start?: number | null;
  pe_end?: number | null;
  implied_growth_pct?: number | null;
  factor_keys_used?: string[];
  partial?: boolean;
  gaps?: string[];
  point_in_time?: boolean;
}

export interface ThesisOut {
  claim: string;
  evidence_ids?: string[];
  monitors?: string[];
  invalidate_if?: string[];
  horizon?: string;
  scenarios?: Record<string, string> | null;
  partial?: boolean;
}

export interface DeepAnalysisOut {
  impact?: ImpactOut | null;
  pricing?: PricingBridgeOut | null;
  thesis?: ThesisOut | null;
}

export interface ResearchReport {
  id?: number | null;
  symbol: string;
  name: string;
  composite_score: number;
  composite_confidence?: string;
  bias: string;
  summary: string;
  brief_summary?: string;
  viewpoints?: Record<string, string>;
  data_gaps?: string[];
  follow_up_questions?: string[];
  news_text_factor?: string | null;
  text_factor_summary?: string | null;
  ashare_factors?: AshareFactor[];
  factors?: NumericFactor[];
  bars_provenance?: BarsProvenance | null;
  dimension_weights?: Record<string, number>;
  analysis_depth?: "standard" | "comprehensive" | "deep";
  factors_expanded?: boolean;
  factor_alignment_note?: string | null;
  enable_signal_verify_hook?: boolean;
  post_hoc?: ReportPostHocHorizon[];
  dimensions?: Record<string, DimensionResult>;
  debate?: DebateResult | null;
  master_commentary?: MasterCommentaryItem[];
  deep_analysis?: DeepAnalysisOut | null;
  disclaimer?: string;
  cached?: boolean;
}

async function downloadReportBlob(
  path: string,
  report: ResearchReport,
  filename: string,
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...dataSourceRequestHeaders(),
  };
  const resp = await fetchWithRetry(apiUrl(path), {
    method: "POST",
    headers,
    body: JSON.stringify(report),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(formatApiDetail(err.detail) || "下载失败");
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export interface PortfolioMetrics {
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  volatility: number;
  concentration_ratio: number;
  concentration_sector?: string | null;
  individual_drawdowns: {
    name?: string;
    cost_price?: number;
    current_price?: number;
    drawdown_pct?: number;
  }[];
  calmar_ratio: number;
  information_ratio: number;
  max_loss_1d: number;
  max_loss_1d_pct: number;
  expected_loss: number;
  expected_loss_pct: number;
  sector_weights?: { sector?: string; weight?: number; value?: number }[];
  top_holding_weight?: number;
  top_holding_symbol?: string | null;
  top_holding_name?: string | null;
}

export interface StressResult {
  id: string;
  name: string;
  pnl: number;
  pnl_pct: number;
  shocked_value?: number;
}

export interface RiskCheckup {
  portfolio_summary: string;
  alerts: {
    rule_id: string;
    severity: string;
    human_message: string;
    symbol?: string | null;
  }[];
  llm_analysis?: {
    market_assessment: string;
    correlation_analysis: string;
    risk_narrative: string;
    scenario_analysis: string[];
  };
  metrics?: PortfolioMetrics;
  var_result?: {
    confidence_level: number;
    time_horizon_days: number;
    method: string;
    var_value: number;
    var_pct: number;
    cvar_value: number;
    cvar_pct: number;
    holdings_var: {
      name: string;
      symbol?: string;
      weight: number;
      var_value: number;
    }[];
  };
  stress_results?: StressResult[];
  master_commentary?: MasterCommentaryItem[];
}

export interface AssetAllocation {
  risk_tolerance: "conservative" | "moderate" | "aggressive";
  risk_label: string;
  allocation: Record<string, number>;
  rationale: string;
  cash_flow_impact?: string;
  emergency_fund_note?: string;
  disclaimer: string;
}

export interface AllocationDeviationRow {
  sector: string;
  actual: number;
  target: number;
  delta: number;
}

export interface AllocationDeviation {
  actual: Record<string, number>;
  targets: Record<string, number>;
  rows: AllocationDeviationRow[];
  notes?: string[];
  disclaimer?: string;
}

export interface MarketOverview {
  indices: {
    name: string;
    symbol?: string;
    price: number;
    change_pct: number;
  }[];
  northbound_net_yi: number | null;
  advancers: number | null;
  decliners: number | null;
  source: string;
  data_status: string;
}

export interface SentimentDriver {
  label: string;
  value: string;
  impact: string;
}

export interface SentimentData {
  score: number;
  label: string;
  drivers: SentimentDriver[];
  source: string;
}

export interface ProviderStatus {
  domain: string;
  primary: string;
  fallback: string | null;
  primary_count: number;
  fallback_count: number;
  degraded: boolean;
  message: string | null;
  updated_at: string | null;
  layer?: string;
  latency_ms?: number | null;
  is_cached?: boolean;
  is_mock?: boolean;
  degraded_reason?: string | null;
  confidence?: DataConfidence;
}

export type DataConfidence =
  | "verified"
  | "single_source"
  | "delayed"
  | "cached"
  | "conflict"
  | "missing";

export type DataSourceDetailStatus =
  | "ok"
  | "degraded"
  | "missing"
  | "mock"
  | "configured"
  | "not_configured";

export interface DataSourceDetail {
  domain: string;
  label: string;
  layer: string;
  source: string;
  fetched_at: string | null;
  latency_ms: number | null;
  is_cached: boolean;
  is_mock: boolean;
  degraded: boolean;
  degraded_reason: string | null;
  confidence: DataConfidence;
  conflict_with: string[];
  status: DataSourceDetailStatus;
}

export interface QuotePriceConflict {
  symbol: string;
  name: string;
  primary_source: string;
  primary_price: number;
  compare_source: string;
  compare_price: number;
  diff_pct: number;
}

export interface DataSourceStatus {
  quotes: ProviderStatus | null;
  overview: ProviderStatus | null;
  details: DataSourceDetail[];
  use_mock: boolean;
  tushare_configured?: boolean;
  tushare_available?: boolean;
  tushare_status?: "no_token" | "unavailable" | "invalid" | "ok" | "quota";
  price_conflicts?: QuotePriceConflict[];
}

export interface ResearchReportListItem {
  id: number;
  symbol: string;
  name: string;
  composite_score: number;
  bias: string;
  summary: string;
  has_debate: boolean;
  created_at: string;
}

export interface StockQuoteOut {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  open?: number;
}

export interface WatchlistItem {
  id: number;
  symbol: string;
  name: string;
}

export interface SectorBoard {
  code: string;
  name: string;
  change_pct: number;
  leader_name: string;
  leader_symbol: string;
  leader_change_pct: number;
}

export interface SectorMovers {
  gainers: SectorBoard[];
  losers: SectorBoard[];
  boards?: SectorBoard[];
  updated_at: string;
  disclaimer: string;
}

export interface SectorBoardsAll {
  boards: SectorBoard[];
  updated_at: string;
  disclaimer: string;
}

export interface IntradayPoint {
  time: string;
  price: number;
}

export interface IndexIntraday {
  symbol: string;
  points: IntradayPoint[];
}

export interface PriceAlertSettings {
  enabled: boolean;
  threshold_pct: number;
}

export interface PriceAlertNotification {
  id: number;
  symbol: string;
  name: string;
  change_pct: number;
  threshold_pct: number;
  trading_date: string;
  message: string;
  read: boolean;
  created_at: string;
}

export interface SignalBacktestHorizon {
  days: number;
  sample_count: number;
  bullish_count: number;
  bearish_count: number;
  bullish_avg_return_pct: number | null;
  bearish_avg_return_pct: number | null;
  bullish_median_return_pct?: number | null;
  bearish_median_return_pct?: number | null;
  bullish_positive_rate_pct: number | null;
  bearish_negative_rate_pct: number | null;
  spread_avg_return_pct?: number | null;
  bias_bullish_avg_return_pct?: number | null;
  bias_bearish_avg_return_pct?: number | null;
  factor_tilt_bullish_avg_return_pct?: number | null;
  factor_tilt_bearish_avg_return_pct?: number | null;
}

export interface SignalBacktest {
  horizons: SignalBacktestHorizon[];
  disclaimer: string;
  label?: string;
  notes?: string[];
  sample_bias_note?: string;
  unique_symbols?: number;
  bias_sample_count?: number;
  factor_tilt_sample_count?: number;
}

export interface MemorySearchHit {
  report_id: number;
  symbol: string;
  name: string;
  bias: string;
  summary: string;
  composite_score: number;
  created_at: string;
}

export interface MemorySearchResult {
  query: string;
  hits: MemorySearchHit[];
}

export interface BriefingSection {
  title: string;
  content: string;
}

export interface Briefing {
  kind: "premarket" | "intraday" | "postmarket";
  title: string;
  sections: BriefingSection[];
  summary: string;
  disclaimer: string;
  generated_at: string;
}

export interface BriefingSchedule {
  enabled: boolean;
  premarket_time: string;
  intraday_time: string;
  postmarket_time: string;
  morning_time: string;
  closing_time: string;
  timezone: string;
}

export interface ActionSignal {
  type: "price" | "news" | "risk" | "fundamental" | "market" | "research" | "info";
  severity: "critical" | "warning" | "info";
  title: string;
  detail: string;
  action: string;
  action_target: string;
  symbol: string | null;
  weight: number;
}

export interface DailyActionCenter {
  signals: ActionSignal[];
  summary: string;
}

export interface ChartOverlayPoint {
  time: string;
  price: number;
}

export interface ChartOverlay {
  id: string;
  kind: "trend" | "level";
  a?: ChartOverlayPoint;
  b?: ChartOverlayPoint;
  side?: "support" | "resistance";
  price?: number;
  strength: number;
  touches?: number;
  source: "algo" | "ai";
  rationale?: string;
}

export interface ChartOverlaySet {
  symbol: string;
  generatedAt: string;
  overlays: ChartOverlay[];
}

export interface KlineChart {
  symbol: string;
  days: number;
  bars: {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }[];
  source?: string;
  adjust?: string;
  indicators: {
    ma20: (number | null)[];
    rsi: (number | null)[];
    macd: (number | null)[];
    macd_signal: (number | null)[];
    macd_histogram: (number | null)[];
    boll_mid?: (number | null)[];
    boll_upper?: (number | null)[];
    boll_lower?: (number | null)[];
    atr?: (number | null)[];
    kdj_k?: (number | null)[];
    kdj_d?: (number | null)[];
    kdj_j?: (number | null)[];
  };
}

// ── News Deep Analysis ──

export interface NewsAnalysisStockImpact {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  pe_ttm: number | null;
  technical_signal: string;
  technical_summary: string;
  fundamental_summary: string;
  sentiment_summary: string;
  impact_assessment: string;
  impact_direction: "positive" | "negative" | "neutral";
  key_points: string[];
}

export interface NewsAnalysis {
  news_id: number;
  title: string;
  summary: string;
  source: string;
  entities: string[];
  related_stocks: NewsAnalysisStockImpact[];
  market_context: string;
  cross_analysis: string;
  overall_assessment: string;
  disclaimer: string;
}
