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

export type StreamEvent = AgentStreamEvent;

export type ExecutionPreference = "react" | "plan_execute" | "preset" | "auto";

export interface ChatStreamOptions {
  confirmedSymbol?: string;
  confirmedName?: string;
  executionPreference?: ExecutionPreference;
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
  partial?: boolean;
  follow_up_questions?: string[];
  disclaimer: string;
  llm_usage?: LlmUsage | null;
}

export interface GlossaryTerm {
  id: string;
  short: string;
  en: string;
  def: string;
  analogy: string;
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
  entities: string[];
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

export interface DimensionResult {
  agent: string;
  score: number;
  confidence: string;
  highlights: string[];
  risks: string[];
  data_sources: string[];
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

export interface ResearchReport {
  symbol: string;
  name: string;
  composite_score: number;
  composite_confidence?: string;
  bias: string;
  summary: string;
  viewpoints?: Record<string, string>;
  data_gaps?: string[];
  follow_up_questions?: string[];
  news_text_factor?: string | null;
  text_factor_summary?: string | null;
  ashare_factors?: AshareFactor[];
  dimension_weights?: Record<string, number>;
  dimensions: Record<string, DimensionResult>;
  debate?: DebateResult | null;
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

export interface AssetAllocation {
  risk_tolerance: "conservative" | "moderate" | "aggressive";
  risk_label: string;
  allocation: Record<string, number>;
  rationale: string;
  cash_flow_impact?: string;
  emergency_fund_note?: string;
  disclaimer: string;
}

export interface MarketOverview {
  indices: { name: string; symbol?: string; price: number; change_pct: number }[];
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
  layer?: string;
  latency_ms?: number | null;
  is_cached?: boolean;
  is_mock?: boolean;
  degraded_reason?: string | null;
  confidence?: DataConfidence;
}

export type DataConfidence = "verified" | "single_source" | "delayed" | "cached" | "conflict" | "missing";

export type DataSourceDetailStatus = "ok" | "degraded" | "missing" | "mock" | "configured" | "not_configured";

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

export interface DataSourceStatus {
  quotes: ProviderStatus | null;
  overview: ProviderStatus | null;
  details: DataSourceDetail[];
  provider_catalog?: ProviderMeta[];
  use_mock: boolean;
  tushare_configured?: boolean;
  tushare_available?: boolean;
}

export interface ProviderMeta {
  key: string;
  label: string;
  layer: string;
  provider: string;
  domain: string;
  default_ttl_seconds?: number | null;
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

export interface ActionSignal {
  type: "price" | "news" | "risk" | "fundamental" | "info";
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
  generated_at: string;
  disclaimer: string;
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
