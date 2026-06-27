import { analysisBodyField } from "../analysisSettings";
import { createJsonSseStream } from "../apiSse";
import { llmBodyField } from "../llmSettings";
import type { ModeSettingsApiPayload } from "../modeSettings";
import {
  apiUrl,
  checkBackendHealth,
  llmFormToApiBody,
  llmRequestHeaders,
  request,
  requestPlain,
  requestWithLlm,
  type LlmSettingsMeta,
  type LlmTestResult,
  type LlmUserSettings,
} from "./client";
import type {
  AgentStreamEvent,
  AssetAllocation,
  Briefing,
  ChatResponse,
  ChatStreamOptions,
  DailyActionCenter,
  DataSourceStatus,
  ExecutionPreference,
  GlossaryTerm,
  Holding,
  HoldingCreatePayload,
  HoldingEnriched,
  KlineChart,
  MarketOverview,
  MemorySearchResult,
  NewsAnalysis,
  NewsIngestOut,
  NewsItem,
  ResearchReport,
  ResearchReportListItem,
  RiskCheckup,
  SectorPreferences,
  SignalBacktest,
  StockLookupOut,
  StockQuoteOut,
} from "./types";

export const apiEndpoints = {
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
  ) =>
    createJsonSseStream<ChatResponse, AgentStreamEvent>({
      url: apiUrl("/chat/stream"),
      method: "POST",
      headers: llmRequestHeaders(),
      body: {
        message,
        session_id: sessionId,
        confirmed_symbol: options?.confirmedSymbol,
        confirmed_name: options?.confirmedName,
        execution_preference: options?.executionPreference,
        ...analysisBodyField(),
        ...llmBodyField(),
      },
      onEvent,
      extractResult: (event) =>
        event.type === "done" && event.response ? (event.response as ChatResponse) : undefined,
    }),
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
    createJsonSseStream<ResearchReport, AgentStreamEvent>({
      url: apiUrl(`/research/analyze/stream?symbol=${symbol}`),
      headers: llmRequestHeaders(),
      onEvent,
      extractResult: (event) =>
        event.type === "done" && event.result ? (event.result as unknown as ResearchReport) : undefined,
    }),
  riskCheckup: () =>
    requestWithLlm<RiskCheckup>(
      "/risk/checkup",
      {
        method: "POST",
        body: JSON.stringify({ ...analysisBodyField() }),
      },
      120_000,
    ),
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
          ...analysisBodyField(),
        }),
      },
      60_000,
    ),
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
    requestWithLlm<Briefing>(`/briefing/generate?kind=${kind}`, { method: "POST" }),
  loadDemo: () => request<{ status: string; count: number; demo: boolean }>("/portfolio/demo", { method: "POST" }),
  clearDemo: () => request<{ status: string; deleted: number }>("/portfolio/demo", { method: "DELETE" }),
  demoStatus: () => request<{ demo: boolean }>("/portfolio/demo/status"),
  dailyActions: () => request<DailyActionCenter>("/action-center/daily"),
  glossary: () => request<Record<string, GlossaryTerm>>("/settings/glossary"),
  analyzeNews: (
    newsId: number,
    symbol: string,
    onEvent?: (event: AgentStreamEvent) => void,
    signal?: AbortSignal,
  ) =>
    createJsonSseStream<NewsAnalysis, AgentStreamEvent>({
      url: apiUrl(`/news/${newsId}/analyze/stream?symbol=${symbol}`),
      headers: llmRequestHeaders(),
      signal,
      onEvent,
      extractResult: (event) =>
        event.type === "done" && event.result ? (event.result as unknown as NewsAnalysis) : undefined,
    }),
};

export const api = {
  ...apiEndpoints,
  health: checkBackendHealth,
};
