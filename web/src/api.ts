const API = "/api/v1";
const DEFAULT_TIMEOUT_MS = 20000;

async function request<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const url = `${API}${path}`;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(url, { ...options, headers, signal: controller.signal });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      const detail =
        typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail ?? err);
      if (resp.status === 404) {
        throw new Error(
          `接口不存在 (404): ${url}。请确认后端已启动且已 reload；UI 请访问 http://localhost:5174`,
        );
      }
      throw new Error(`${detail} [${resp.status} ${path}]`);
    }
    const text = await resp.text();
    if (!text) return undefined as T;
    return JSON.parse(text) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`请求超时 (${Math.round(timeoutMs / 1000)}s): ${path}`);
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

export const api = {
  chat: (message: string, sessionId?: string) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId }),
    }),
  holdings: () => request<Holding[]>("/portfolio/holdings"),
  lookupStock: (query: string) =>
    request<StockLookupResult>("/portfolio/holdings/lookup", {
      method: "POST",
      body: JSON.stringify({ query }),
    }, 5000),
  addHolding: (h: HoldingInput) =>
    request<Holding>("/portfolio/holdings", { method: "POST", body: JSON.stringify(h) }),
  confirmHolding: (h: HoldingConfirmInput) =>
    request<Holding>("/portfolio/holdings/confirm", {
      method: "POST",
      body: JSON.stringify(h),
    }),
  deleteHolding: (id: number) =>
    request(`/portfolio/holdings/${id}`, { method: "DELETE" }),
  backfillSectors: () =>
    request<SectorBackfillResult>("/portfolio/holdings/backfill-sectors", { method: "POST" }, 30000),
  newsFeed: () => request<NewsItem[]>("/news/feed"),
  sectorPrefs: () => request<SectorPreferences>("/news/sectors"),
  updateSectorPrefs: (sectors: string[]) =>
    request<SectorPreferences>("/news/sectors", {
      method: "PUT",
      body: JSON.stringify({ sectors }),
    }),
  ingestNews: () =>
    request<NewsIngestResult>("/news/ingest?limit=20", { method: "POST" }, 90000),
  research: (symbol: string) =>
    request<ResearchReport>(`/research/analyze?symbol=${symbol}`, {}, 120000),
  researchStream: async (
    symbol: string,
    onEvent: (event: AgentStreamEvent) => void,
  ): Promise<AgentStreamEvent | null> =>
    consumeSse(`${API}/research/analyze/stream?symbol=${symbol}`, onEvent),
  chatStream: async (
    message: string,
    sessionId: string | undefined,
    onEvent: (event: AgentStreamEvent) => void,
  ): Promise<AgentStreamEvent | null> =>
    consumeSse(`${API}/chat/stream`, onEvent, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    }),
  riskCheckup: () =>
    request<RiskCheckup>("/risk/checkup", { method: "POST" }, 120000),
  riskCheckupStream: async (
    onEvent: (event: AgentStreamEvent) => void,
  ): Promise<RiskCheckup | null> => {
    const done = await consumeSse(`${API}/risk/checkup/stream`, onEvent, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    return (done?.result as RiskCheckup | undefined) ?? null;
  },
  marketOverview: () => request<MarketOverview>("/market/overview", {}, 8000),
  stockQuotes: (symbols?: string) =>
    request<StockQuote[]>(
      `/market/quotes${symbols ? `?symbols=${symbols}` : ""}`,
      {},
      8000,
    ),
};

export interface ChatResponse {
  session_id: string;
  reply: string;
  cards: Card[];
  intent: string;
  disclaimer: string;
}

export interface Card {
  type: "news" | "research" | "risk" | "text" | "market";
  data: Record<string, unknown>;
}

export interface HoldingInput {
  query?: string;
  symbol?: string;
  name?: string;
  cost_price: number;
  lots?: number;
  quantity?: number;
  sector?: string;
}

export interface HoldingConfirmInput {
  symbol: string;
  name: string;
  cost_price: number;
  lots: number;
  sector?: string;
}

export interface StockCandidate {
  symbol: string;
  name: string;
}

export interface StockLookupResult {
  status: "confirmed" | "ambiguous" | "not_found";
  symbol: string | null;
  name: string | null;
  sector: string | null;
  message: string;
  candidates: StockCandidate[];
  normalized_query: string;
}

export interface Holding {
  id?: number;
  symbol: string;
  name: string;
  cost_price: number;
  quantity: number;
  sector: string;
}

export interface SectorBackfillResult {
  updated: number;
  skipped: number;
  message: string;
}

export interface NewsIngestResult {
  inserted: number;
  scanned: number;
  skipped: number;
  purged: number;
  message: string;
}

export interface HoldingAction {
  symbol: string;
  name: string;
  action: string;
  reason: string;
  priority?: string;
}

export interface AgentStreamEvent {
  type: string;
  message?: string;
  stream_id?: string;
  delta?: string;
  intent?: string;
  agent_id?: string;
  agent_name?: string;
  role?: string;
  content?: string;
  round?: number;
  bull?: string;
  bear?: string;
  verdict?: string;
  risk_level?: string;
  position_action?: string;
  summary?: string;
  reason?: string;
  divergence?: string;
  analysis_process?: string;
  holding_actions?: HoldingAction[];
  vote?: string;
  bullish?: number;
  bearish?: number;
  neutral?: number;
  neutral_view?: string;
  leading?: string;
  aggressive?: string;
  conservative?: string;
  result?: RiskCheckup | ResearchReport;
  response?: ChatResponse;
}

async function consumeSse(
  url: string,
  onEvent: (event: AgentStreamEvent) => void,
  init?: RequestInit,
): Promise<AgentStreamEvent | null> {
  const resp = await fetch(url, init);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : resp.statusText);
  }
  const reader = resp.body?.getReader();
  if (!reader) throw new Error("流式响应不可用");
  const decoder = new TextDecoder();
  let buffer = "";
  let lastDone: AgentStreamEvent | null = null;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;
      const event = JSON.parse(line.slice(6)) as AgentStreamEvent;
      onEvent(event);
      if (event.type === "done") {
        lastDone = event;
      }
    }
  }
  return lastDone;
}

export interface NewsItem {
  title: string;
  summary: string;
  sentiment: string;
  impact_level: string;
  related_to_user: boolean;
  category: "market" | "sector" | "holding";
}

export interface SectorPreferences {
  available: string[];
  selected: string[];
}

export interface DebateResult {
  rounds: { round: number; bull_argument: string; bear_rebuttal: string }[];
  judge_verdict: string;
  consensus: string;
  core_divergence: string;
  final_bias: string;
  confidence: string;
  vote_tally?: Record<string, number>;
  manager_thesis?: string;
}

export interface ResearchReport {
  symbol: string;
  name: string;
  composite_score: number;
  bias: string;
  summary: string;
  debate?: DebateResult;
  dimensions: Record<string, { score: number; highlights: string[]; risks: string[] }>;
}

export interface RiskCheckup {
  alerts: { rule_id: string; severity: string; message: string; human_message: string }[];
  portfolio_summary: string;
  llm_analysis?: {
    market_assessment: string;
    correlation_analysis: string;
    risk_narrative: string;
    scenario_analysis: string[];
    risk_level?: string;
    position_action?: string;
    analysis_process?: string;
    holding_actions?: HoldingAction[];
  };
}

export interface IndexQuote {
  name: string;
  symbol: string;
  price: number;
  change_pct: number;
}

export interface StockQuote {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  high: number;
  low: number;
  volume: number;
  sector: string;
}

export interface MarketOverview {
  indices: IndexQuote[];
  northbound_net_yi: number | null;
  advancers: number | null;
  decliners: number | null;
  source: string;
  data_status: "live" | "mock" | "unavailable";
  message?: string | null;
  updated_at: string;
}
