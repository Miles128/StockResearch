import { analysisBodyField } from "./analysisSettings";
import { dataSourceRequestHeaders } from "./dataSourceSettings";
import {
  llmBodyField,
  llmFormToApiBody,
  llmRequestHeaders,
  type LlmSettingsMeta,
  type LlmTestResult,
  type LlmUserSettings,
} from "./llmSettings";

export type { LlmSettingsMeta };

/** Build-time optional origin, e.g. https://api.example.com (no trailing slash). */
const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const API = API_ORIGIN ? `${API_ORIGIN}/api/v1` : "/api/v1";

function apiUrl(path: string): string {
  return `${API}${path}`;
}

function formatApiDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item)))
      .join("; ");
  }
  return "";
}

async function requestPlain<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const resp = await fetch(`${API}${path}`, { ...options, headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(formatApiDetail(err.detail) || "请求失败");
  }
  return resp.json();
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...llmRequestHeaders(),
    ...dataSourceRequestHeaders(),
    ...(options.headers as Record<string, string>),
  };

  const resp = await fetch(`${API}${path}`, { ...options, headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(formatApiDetail(err.detail) || "请求失败");
  }
  return resp.json();
}

export interface AgentStreamEvent {
  type: string;
  message?: string;
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
}

export interface HoldingAction {
  symbol: string;
  name: string;
  action: string;
  reason: string;
  priority?: string;
}

export type StreamEvent = AgentStreamEvent;

async function consumeSse(
  resp: Response,
  onEvent?: (event: AgentStreamEvent) => void,
): Promise<void> {
  if (!resp.body) {
    throw new Error("流式请求失败");
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const jsonStr = line.slice(6).trim();
      if (!jsonStr || jsonStr === "[DONE]") continue;
      try {
        const event = JSON.parse(jsonStr) as AgentStreamEvent;
        onEvent?.(event);
      } catch {
        // skip malformed JSON
      }
    }
  }
}

export type ExecutionPreference = "react" | "plan_execute" | "preset" | "auto";

export interface ChatStreamOptions {
  confirmedSymbol?: string;
  confirmedName?: string;
  executionPreference?: ExecutionPreference;
}

async function streamChat(
  message: string,
  sessionId?: string,
  onEvent?: (event: AgentStreamEvent) => void,
  options?: ChatStreamOptions,
): Promise<ChatResponse | null> {
  const resp = await fetch(apiUrl("/chat/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...llmRequestHeaders() },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      confirmed_symbol: options?.confirmedSymbol,
      confirmed_name: options?.confirmedName,
      execution_preference: options?.executionPreference,
      ...analysisBodyField(),
      ...llmBodyField(),
    }),
  });
  if (!resp.ok) {
    throw new Error("流式请求失败");
  }

  let finalResponse: ChatResponse | null = null;
  await consumeSse(resp, (event) => {
    onEvent?.(event);
    if (event.type === "done" && event.response) {
      finalResponse = event.response as ChatResponse;
    }
  });
  return finalResponse;
}

export const api = {
  llmSettings: () => request<LlmSettingsMeta>("/settings/llm"),
  testLlmConnection: (form: LlmUserSettings) =>
    requestPlain<LlmTestResult>("/settings/llm/test", {
      method: "POST",
      body: JSON.stringify(llmFormToApiBody(form)),
    }),
  chat: (message: string, sessionId?: string, options?: ChatStreamOptions) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        session_id: sessionId,
        confirmed_symbol: options?.confirmedSymbol,
        confirmed_name: options?.confirmedName,
        execution_preference: options?.executionPreference,
        ...analysisBodyField(),
        ...llmBodyField(),
      }),
    }),
  chatStream: (
    message: string,
    sessionId?: string,
    onEvent?: (event: AgentStreamEvent) => void,
    options?: ChatStreamOptions,
  ) => streamChat(message, sessionId, onEvent, options),
  holdings: () => request<Holding[]>("/portfolio/holdings"),
  holdingsEnriched: () => request<HoldingEnriched[]>("/portfolio/holdings/enriched"),
  addHolding: (h: HoldingCreatePayload) =>
    request("/portfolio/holdings", { method: "POST", body: JSON.stringify(h) }),
  deleteHolding: (id: number) =>
    request(`/portfolio/holdings/${id}`, { method: "DELETE" }),
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
  ingestNews: () => request<NewsIngestOut>("/news/ingest?limit=10", { method: "POST" }),
  research: (symbol: string) => request<ResearchReport>(`/research/analyze?symbol=${symbol}`),
  researchStream: (symbol: string, onEvent?: (event: AgentStreamEvent) => void) =>
    streamResearch(symbol, onEvent),
  riskCheckup: () => request<RiskCheckup>("/risk/checkup", { method: "POST" }),
  marketOverview: () => request<MarketOverview>("/market/overview"),
  stockQuotes: (symbols: string) => request<StockQuoteOut[]>(`/market/quotes?symbols=${symbols}`),
  dataSourceStatus: () => request<DataSourceStatus>("/market/data-status"),
  klineChart: (symbol: string, days = 60) =>
    request<KlineChart>(`/market/kline?symbol=${symbol}&days=${days}`),
  listReports: () => request<ResearchReportListItem[]>("/research/reports"),
  downloadReportMarkdown: (id: number) => {
    window.open(apiUrl(`/research/reports/${id}/markdown`), "_blank", "noopener,noreferrer");
  },
  downloadReportPdf: (id: number) => {
    window.open(apiUrl(`/research/reports/${id}/pdf`), "_blank", "noopener,noreferrer");
  },
  signalBacktest: () => request<SignalBacktest>("/research/signal-backtest"),
  searchMemory: (q: string) =>
    request<MemorySearchResult>(`/research/memory/search?q=${encodeURIComponent(q)}`),
  generateBriefing: (kind: "morning" | "closing") =>
    request<Briefing>(`/briefing/generate?kind=${kind}`, { method: "POST" }),
};

async function streamResearch(
  symbol: string,
  onEvent?: (event: AgentStreamEvent) => void,
): Promise<ResearchReport | null> {
  const resp = await fetch(apiUrl(`/research/analyze/stream?symbol=${symbol}`), {
    headers: llmRequestHeaders(),
  });
  if (!resp.ok) {
    throw new Error("投研流式请求失败");
  }
  let report: ResearchReport | null = null;
  await consumeSse(resp, (event) => {
    onEvent?.(event);
    if (event.type === "done" && event.result) {
      report = event.result as unknown as ResearchReport;
    }
  });
  return report;
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
  label: string;
  description: string;
}

export interface RouteChoiceCardData {
  message: string;
  original_message: string;
  finance_related: boolean;
  preset_mode: string | null;
  preset_label: string | null;
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
    | "route_choice";
  data: Record<string, unknown>;
}

export interface HoldingEnriched extends Holding {
  price?: number | null;
  change_pct?: number | null;
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
  category: "market" | "sector" | "holding";
  published_at: string;
}

export interface SectorPreferences {
  available: string[];
  selected: string[];
}

export interface NewsIngestOut {
  inserted: number;
  scanned: number;
  skipped: number;
  message: string;
}

export interface ResearchReport {
  symbol: string;
  name: string;
  composite_score: number;
  bias: string;
  summary: string;
  dimensions: Record<string, { score: number; highlights: string[]; risks: string[] }>;
  debate?: {
    consensus: string;
    final_bias: string;
    judge_verdict: string;
  };
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
}

export interface RiskCheckup {
  portfolio_summary: string;
  alerts: { rule_id: string; severity: string; human_message: string }[];
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
    holdings_var: { name: string; weight: number; var_value: number }[];
  };
}

export interface MarketOverview {
  indices: { name: string; price: number; change_pct: number }[];
  northbound_net_yi: number | null;
  advancers: number | null;
  decliners: number | null;
  source: string;
  data_status: string;
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
}

export interface DataSourceStatus {
  quotes: ProviderStatus | null;
  overview: ProviderStatus | null;
  use_mock: boolean;
  tushare_configured?: boolean;
  tushare_available?: boolean;
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
}

export interface SignalBacktestHorizon {
  days: number;
  sample_count: number;
  bullish_count: number;
  bearish_count: number;
  bullish_avg_return_pct: number | null;
  bearish_avg_return_pct: number | null;
  bullish_positive_rate_pct: number | null;
  bearish_negative_rate_pct: number | null;
}

export interface SignalBacktest {
  horizons: SignalBacktestHorizon[];
  disclaimer: string;
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
  kind: "morning" | "closing";
  title: string;
  sections: BriefingSection[];
  summary: string;
  disclaimer: string;
  generated_at: string;
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
  indicators: {
    ma20: (number | null)[];
    rsi: (number | null)[];
    macd: (number | null)[];
    macd_signal: (number | null)[];
    macd_histogram: (number | null)[];
  };
}
