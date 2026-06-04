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

export type AnalysisMode = "simple" | "complex";

async function streamChat(
  message: string,
  sessionId?: string,
  onEvent?: (event: AgentStreamEvent) => void,
  analysisMode?: AnalysisMode,
): Promise<ChatResponse | null> {
  const resp = await fetch(apiUrl("/chat/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...llmRequestHeaders() },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      analysis_mode: analysisMode ?? null,
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
  chat: (message: string, sessionId?: string, analysisMode?: AnalysisMode) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        session_id: sessionId,
        analysis_mode: analysisMode ?? null,
        ...llmBodyField(),
      }),
    }),
  chatStream: (
    message: string,
    sessionId?: string,
    onEvent?: (event: AgentStreamEvent) => void,
    analysisMode?: AnalysisMode,
  ) => streamChat(message, sessionId, onEvent, analysisMode),
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
  ingestNews: () => request<NewsIngestOut>("/news/ingest?limit=10", { method: "POST" }),
  research: (symbol: string) => request<ResearchReport>(`/research/analyze?symbol=${symbol}`),
  researchStream: (symbol: string, onEvent?: (event: AgentStreamEvent) => void) =>
    streamResearch(symbol, onEvent),
  riskCheckup: () => request<RiskCheckup>("/risk/checkup", { method: "POST" }),
  marketOverview: () => request<MarketOverview>("/market/overview"),
  stockQuotes: (symbols: string) => request<StockQuoteOut[]>(`/market/quotes?symbols=${symbols}`),
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

export interface ChatResponse {
  session_id: string;
  reply: string;
  cards: Card[];
  intent: string;
  disclaimer: string;
}

export interface Card {
  type: "news" | "research" | "risk" | "text" | "market" | "debate" | "plan" | "financial";
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
  category: string;
  published_at: string;
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

export interface StockQuoteOut {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
}
