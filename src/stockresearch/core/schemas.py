"""Pydantic schemas for API and agents."""

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from stockresearch.core.constants import DISCLAIMER
from stockresearch.services.trading_calendar import validate_buy_date


class HoldingCreate(BaseModel):
    """Accept code/name query or explicit symbol; quantity in 手 (lots)."""

    symbol: str | None = Field(default=None, min_length=6, max_length=6, pattern=r"^\d{6}$")
    name: str | None = Field(default=None, min_length=1, max_length=50)
    query: str | None = Field(default=None, min_length=1, max_length=50)
    cost_price: float = Field(gt=0, description="每股成本价（元）")
    lots: int | None = Field(default=None, gt=0, le=100000, description="持仓手数")
    quantity: int | None = Field(default=None, gt=0, description="股数；若提供 lots 则自动计算")
    sector: str = Field(default="未知", max_length=50)
    buy_date: date | None = Field(default=None, description="买入日期")

    @model_validator(mode="after")
    def require_identifier_and_quantity(self) -> "HoldingCreate":
        if not (self.query or self.symbol or self.name):
            raise ValueError("请提供股票代码或名称（query / symbol / name 三选一）")
        if self.lots is None and self.quantity is None:
            raise ValueError("请提供持仓手数 lots")
        if self.lots is not None:
            object.__setattr__(self, "quantity", self.lots * 100)
        validate_buy_date(self.buy_date)
        return self


class StockLookupRequest(BaseModel):
    query: str = Field(min_length=1, max_length=50)


class StockCandidateOut(BaseModel):
    symbol: str
    name: str


class StockLookupOut(BaseModel):
    status: Literal["confirmed", "ambiguous", "not_found"]
    symbol: str | None = None
    name: str | None = None
    sector: str | None = None
    message: str
    candidates: list[StockCandidateOut] = Field(default_factory=list)
    normalized_query: str


class HoldingConfirmCreate(BaseModel):
    symbol: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    name: str = Field(min_length=1, max_length=50)
    cost_price: float = Field(gt=0)
    lots: int = Field(gt=0, le=100000)
    sector: str = Field(default="未知", max_length=50)
    buy_date: date | None = Field(default=None, description="买入日期")

    @model_validator(mode="after")
    def check_buy_date(self) -> "HoldingConfirmCreate":
        validate_buy_date(self.buy_date)
        return self


class HoldingTransactionItem(BaseModel):
    side: Literal["buy", "sell"]
    symbol: str | None = Field(default=None, min_length=6, max_length=6, pattern=r"^\d{6}$")
    name: str | None = Field(default=None, min_length=1, max_length=50)
    query: str | None = Field(default=None, min_length=1, max_length=50)
    cost_price: float | None = Field(default=None, gt=0, description="买入成交价（元/股）")
    lots: int = Field(gt=0, le=100000, description="手数")
    trade_date: date | None = Field(default=None, description="交易日期")

    @model_validator(mode="after")
    def validate_transaction(self) -> "HoldingTransactionItem":
        if not (self.query or self.symbol or self.name):
            raise ValueError("请提供股票代码或名称")
        if self.side == "buy":
            if self.cost_price is None:
                raise ValueError("买入需填写成交价")
            validate_buy_date(self.trade_date)
        return self


class HoldingTransactionBatch(BaseModel):
    transactions: list[HoldingTransactionItem] = Field(min_length=1, max_length=20)


class HoldingTransactionResult(BaseModel):
    applied: int
    holdings: list["HoldingOut"]


class HoldingOut(BaseModel):
    id: int
    symbol: str
    name: str
    cost_price: float
    quantity: int
    sector: str
    buy_date: date | None = None

    model_config = {"from_attributes": True}


class HoldingEnrichedOut(HoldingOut):
    """Holding with live or closing quote and derived P&L."""

    price: float | None = None
    change_pct: float | None = None
    open: float | None = None
    price_label: str = "收盘"
    market_session: Literal["trading", "closed"] = "closed"
    profit_amount: float | None = None
    profit_pct: float | None = None
    annualized_pct: float | None = None
    quote_available: bool = False


class SectorBackfillOut(BaseModel):
    updated: int
    skipped: int
    message: str


class WatchlistCreate(BaseModel):
    symbol: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    name: str = Field(min_length=1, max_length=50)


class WatchlistOut(BaseModel):
    id: int
    symbol: str
    name: str

    model_config = {"from_attributes": True}


class NewsItemOut(BaseModel):
    id: int
    title: str
    summary: str
    source: str
    sentiment: str
    impact_level: str
    entities: list[str]
    related_to_user: bool
    category: Literal["market", "sector", "holding"] = "market"
    published_at: datetime

    model_config = {"from_attributes": True}


class SectorPreferencesOut(BaseModel):
    available: list[str]
    selected: list[str]


class SectorPreferencesUpdate(BaseModel):
    sectors: list[str] = Field(default_factory=list, max_length=20)


class NewsIngestAcceptedOut(BaseModel):
    """Immediate response when ingest is queued as a background job."""

    job_id: str
    status: Literal["queued"] = "queued"


class NewsIngestJobOut(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    inserted: int = 0
    scanned: int = 0
    skipped: int = 0
    purged: int = 0
    message: str = ""
    error: str | None = None


class NewsIngestOut(BaseModel):
    """Legacy sync ingest payload (kept for compatibility / completed job shape)."""

    inserted: int
    scanned: int
    skipped: int
    purged: int
    message: str


class AnnouncementItemOut(BaseModel):
    """巨潮公告条目。"""

    title: str
    announcement_type: str
    announcement_time: datetime
    symbol: str
    name: str = ""
    url: str = ""
    source: str = "cninfo"


class ResearchReportItemOut(BaseModel):
    """东方财富机构研报条目。"""

    title: str
    institution: str = ""
    analyst: str = ""
    rating: str = ""
    target_price: float | None = None
    publish_date: datetime
    symbol: str
    name: str = ""
    summary: str = ""
    source: str = "eastmoney"


class DimensionEvidence(BaseModel):
    """Verifiable citation attached to a research dimension."""

    source: str
    date: str | None = None
    snippet: str
    url: str | None = None
    kind: Literal["announcement", "research_report", "financial", "other"] = "other"


class DimensionResult(BaseModel):
    agent: str
    score: float = Field(ge=1, le=10)
    confidence: Literal["high", "medium", "low"]
    highlights: list[str]
    risks: list[str]
    data_sources: list[str]
    analysis: str = ""
    evidence: list[DimensionEvidence] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list, max_length=8)
    partial: bool = False


class DebateRound(BaseModel):
    round: int
    bull_argument: str
    bear_rebuttal: str


class DebateResult(BaseModel):
    rounds: list[DebateRound]
    judge_verdict: str
    consensus: str
    core_divergence: str
    final_bias: Literal["bullish", "bearish", "neutral"]
    confidence: Literal["high", "medium", "low"]
    vote_tally: dict[str, int] | None = None
    manager_thesis: str | None = None


class FactorSourceOut(BaseModel):
    key: str
    label: str
    layer: str = "L1"
    provider: str
    status: Literal["verified", "missing"]
    note: str | None = None


class AshareFactorOut(BaseModel):
    """Evidence-coverage checklist item (not a numeric investable factor)."""

    category: str
    name: str
    status: Literal["verified", "partial", "missing"]
    impact: Literal["liquidity", "sentiment", "fundamental", "valuation", "event", "technical"]
    evidence: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    source_details: list[FactorSourceOut] = Field(default_factory=list)


class NumericFactorOut(BaseModel):
    """Computable research factor with optional percentile."""

    key: str
    label: str
    value: float | None = None
    percentile: float | None = None
    as_of: str | None = None
    unit: str = ""
    partial: bool = False
    note: str | None = None
    bars_source: str | None = None
    bars_adjust: str | None = None


class BarsProvenanceOut(BaseModel):
    """OHLCV provenance stamp attached to a research report."""

    source: str = "unknown"
    adjust: str = "none"
    as_of: str | None = None
    partial: bool = False
    note: str | None = None


class SectorLeaderBrief(BaseModel):
    symbol: str
    name: str
    price: float
    change_pct: float
    brief: str


class MasterCommentaryItem(BaseModel):
    master: str
    name: str
    signal: Literal["bullish", "neutral", "bearish"] = "neutral"
    signal_text: str = "中性"
    confidence: float = 0.5
    reasoning: str = ""
    key_metric: str = ""


class ImpactPeakDayOut(BaseModel):
    date: str
    idio_return_pct: float
    event_title: str | None = None
    event_kind: str | None = None  # earnings | risk | other | None
    event_fwd_return_5d_pct: float | None = None
    unexplained: bool = False


class ImpactOut(BaseModel):
    window_trading_days: int = 20
    stock_return_pct: float | None = None
    market_contrib_pct: float | None = None
    industry_contrib_pct: float | None = None
    idio_return_pct: float | None = None
    model: str = "two_step_residual_v1"
    r_squared: float | None = None
    market_symbol: str = "000300"
    industry_proxy: str = "peer_ew"  # peer equal-weight basket
    partial: bool = False
    gaps: list[str] = Field(default_factory=list)
    peak_days: list[ImpactPeakDayOut] = Field(default_factory=list)
    point_in_time: bool = True


class PricingBridgeOut(BaseModel):
    window_label: str = ""
    price_change_pct: float | None = None
    earnings_contrib_pct: float | None = None
    multiple_contrib_pct: float | None = None
    pe_start: float | None = None
    pe_end: float | None = None
    implied_growth_pct: float | None = None
    factor_keys_used: list[str] = Field(default_factory=list)
    partial: bool = False
    gaps: list[str] = Field(default_factory=list)
    point_in_time: bool = True


class ThesisOut(BaseModel):
    claim: str
    evidence_ids: list[str] = Field(default_factory=list)
    monitors: list[str] = Field(default_factory=list)
    invalidate_if: list[str] = Field(default_factory=list)
    horizon: str = ""
    scenarios: dict[str, str] | None = None
    partial: bool = False


class DeepAnalysisOut(BaseModel):
    impact: ImpactOut | None = None
    pricing: PricingBridgeOut | None = None
    thesis: ThesisOut | None = None


class ResearchReportOut(BaseModel):
    symbol: str
    name: str
    dimensions: dict[str, DimensionResult]
    composite_score: float
    composite_confidence: Literal["high", "medium", "low"]
    bias: Literal["bullish", "bearish", "neutral"]
    summary: str
    brief_summary: str = ""
    viewpoints: dict[str, str] = Field(default_factory=dict)
    data_gaps: list[str] = Field(default_factory=list, max_length=5)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=4)
    debate: DebateResult | None = None
    sector: str | None = None
    leaders: list[SectorLeaderBrief] = Field(default_factory=list)
    news_text_factor: str | None = None
    text_factor_summary: str | None = None
    ashare_factors: list[AshareFactorOut] = Field(default_factory=list)
    factors: list[NumericFactorOut] = Field(default_factory=list)
    bars_provenance: BarsProvenanceOut | None = None
    dimension_weights: dict[str, float] = Field(default_factory=dict)
    master_commentary: list[MasterCommentaryItem] = Field(default_factory=list)
    analysis_depth: Literal["standard", "comprehensive", "deep"] = "standard"
    deep_analysis: DeepAnalysisOut | None = None
    factors_expanded: bool = False
    factor_alignment_note: str | None = None
    enable_signal_verify_hook: bool = False
    disclaimer: str = DISCLAIMER
    cached: bool = False
    id: int | None = None
    # Optional post-hoc verification for this report (filled by API when requested)
    post_hoc: list[dict[str, object]] = Field(default_factory=list)


class RiskAlertOut(BaseModel):
    rule_id: str
    severity: str
    symbol: str | None = None
    message: str
    human_message: str


class HoldingActionOut(BaseModel):
    symbol: str
    name: str
    action: str
    reason: str
    priority: str = "中"


class LLMRiskAnalysis(BaseModel):
    market_assessment: str
    correlation_analysis: str
    risk_narrative: str
    scenario_analysis: list[str]
    risk_level: str = ""
    position_action: str = ""
    analysis_process: str = ""
    holding_actions: list[HoldingActionOut] = Field(default_factory=list)


class PortfolioMetricsOut(BaseModel):
    """组合风险指标."""

    sharpe_ratio: float = Field(description="夏普比率")
    sortino_ratio: float = Field(description="索提诺比率")
    max_drawdown: float = Field(description="最大回撤(%)")
    volatility: float = Field(description="年化波动率(%)")
    concentration_ratio: float = Field(description="行业集中度")
    concentration_sector: str | None = Field(default=None, description="集中行业")
    individual_drawdowns: list[dict[str, object]] = Field(default_factory=list)
    calmar_ratio: float = Field(default=0.0, description="Calmar比率")
    information_ratio: float = Field(default=0.0, description="信息比率")
    max_loss_1d: float = Field(default=0.0, description="单日最大可能损失(元)")
    max_loss_1d_pct: float = Field(default=0.0, description="单日最大可能损失(%)")
    expected_loss: float = Field(default=0.0, description="期望损失EL(元)")
    expected_loss_pct: float = Field(default=0.0, description="期望损失EL(%)")
    sector_weights: list[dict[str, object]] = Field(default_factory=list)
    top_holding_weight: float = Field(default=0.0, description="最大个股权重")
    top_holding_symbol: str | None = None
    top_holding_name: str | None = None


class VaRResultOut(BaseModel):
    """VaR 风险价值."""

    confidence_level: float = Field(description="置信水平")
    time_horizon_days: int = Field(description="时间跨度(天)")
    var_value: float = Field(description="VaR 绝对值(元)")
    var_pct: float = Field(description="VaR 占组合比例(%)")
    method: str = Field(default="parametric", description="计算方法")
    holdings_var: list[dict[str, object]] = Field(default_factory=list)
    cvar_value: float = Field(default=0.0, description="CVaR/Expected Shortfall绝对值(元)")
    cvar_pct: float = Field(default=0.0, description="CVaR占组合比例(%)")


class StressResultOut(BaseModel):
    id: str
    name: str
    pnl: float
    pnl_pct: float
    shocked_value: float = 0.0


class RiskCheckupOut(BaseModel):
    alerts: list[RiskAlertOut]
    portfolio_summary: str
    llm_analysis: LLMRiskAnalysis | None = None
    metrics: PortfolioMetricsOut | None = None
    var_result: VaRResultOut | None = None
    stress_results: list[StressResultOut] = Field(default_factory=list)
    master_commentary: list[MasterCommentaryItem] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class LlmUserSettings(BaseModel):
    api_key: str | None = Field(default=None, max_length=256)
    base_url: str | None = Field(default=None, max_length=256)
    model: str | None = Field(default=None, max_length=128)
    temperature: float | None = Field(default=None, ge=0, le=2)
    use_mock: bool | None = None


class LlmSettingsOut(BaseModel):
    default_base_url: str
    default_model: str
    default_api_key: str
    default_temperature: float
    server_use_mock: bool
    server_configured: bool
    server_has_api_key: bool


class CustomMasterOut(BaseModel):
    id: str = Field(min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9_]{0,31}$")
    name: str = Field(min_length=1, max_length=50)
    system_prompt: str = Field(min_length=10, max_length=4000)


class CustomGlossaryTermOut(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    short: str = Field(min_length=1, max_length=50)
    def_: str = Field(min_length=1, max_length=500, serialization_alias="def")
    analogy: str = Field(default="", max_length=300)
    en: str = Field(default="", max_length=100)

    model_config = {"populate_by_name": True}


class ModeSettingsOut(BaseModel):
    mode: Literal["advisor", "research"] = "advisor"
    risk_tolerance: Literal["conservative", "moderate", "aggressive"] = "moderate"
    monthly_income: float | None = Field(default=None, gt=0)
    reading_mode: Literal["friendly", "standard", "professional"] = "friendly"
    analysis_depth: Literal["standard", "comprehensive", "deep"] = "standard"
    enable_debate: bool = False
    enable_glossary: bool = True
    max_signals: int = Field(default=5, ge=1, le=50)
    onboarded: bool = False
    enable_master_commentary: bool = False
    selected_masters: list[str] = Field(default_factory=lambda: ["buffett", "munger", "burry"])
    custom_masters: list[CustomMasterOut] = Field(default_factory=list)
    custom_glossary: list[CustomGlossaryTermOut] = Field(default_factory=list)
    quote_refresh_minutes: int = Field(default=10, ge=1, le=120)
    briefing_auto_enabled: bool = True
    ui_polling_enabled: bool = False


class ModeSettingsUpdate(ModeSettingsOut):
    pass


class LlmTestOut(BaseModel):
    ok: bool
    message: str


class RiskCheckupRequest(BaseModel):
    reading_mode: Literal["friendly", "standard", "professional"] | None = None
    output_locale: Literal["zh", "en"] | None = None
    enable_master_commentary: bool | None = None
    enable_llm_analysis: bool | None = None


class ChatUserContext(BaseModel):
    kind: Literal["focus", "risk", "news", "stock", "report"]
    label: str = Field(min_length=1, max_length=120)
    detail: str | None = Field(default=None, max_length=500)
    symbol: str | None = Field(default=None, min_length=6, max_length=6, pattern=r"^\d{6}$")
    metadata: dict[str, str] | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    user_context: ChatUserContext | None = None
    llm: LlmUserSettings | None = None
    enable_debate: bool | None = None
    enable_master_commentary: bool | None = None
    enable_glossary: bool | None = None
    reading_mode: Literal["friendly", "standard", "professional"] | None = None
    output_locale: Literal["zh", "en"] | None = None
    confirmed_symbol: str | None = Field(
        default=None, min_length=6, max_length=6, pattern=r"^\d{6}$"
    )
    confirmed_name: str | None = Field(default=None, min_length=1, max_length=50)
    execution_preference: Literal["react", "plan_execute", "preset", "auto"] | None = None


class CardPayload(BaseModel):
    type: Literal[
        "news",
        "research",
        "risk",
        "text",
        "market",
        "debate",
        "plan",
        "financial",
        "stock_choice",
    ]
    data: dict[str, object]


class IndexQuoteOut(BaseModel):
    name: str
    symbol: str
    price: float
    change_pct: float


class IntradayPointOut(BaseModel):
    time: str
    price: float


class IndexIntradayOut(BaseModel):
    symbol: str
    points: list[IntradayPointOut]


class StockQuoteOut(BaseModel):
    symbol: str
    name: str
    price: float
    change_pct: float
    open: float = 0
    high: float
    low: float
    volume: float
    sector: str = "未知"
    source: str = "live"


class KlineBarOut(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class KlineIndicatorsOut(BaseModel):
    ma20: list[float | None]
    rsi: list[float | None]
    macd: list[float | None]
    macd_signal: list[float | None]
    macd_histogram: list[float | None]
    boll_mid: list[float | None] = Field(default_factory=list)
    boll_upper: list[float | None] = Field(default_factory=list)
    boll_lower: list[float | None] = Field(default_factory=list)
    atr: list[float | None] = Field(default_factory=list)
    kdj_k: list[float | None] = Field(default_factory=list)
    kdj_d: list[float | None] = Field(default_factory=list)
    kdj_j: list[float | None] = Field(default_factory=list)


class KlineChartOut(BaseModel):
    symbol: str
    days: int
    bars: list[KlineBarOut]
    indicators: KlineIndicatorsOut
    source: str = "unknown"
    adjust: str = "none"  # qfq | none


class MarketOverviewOut(BaseModel):
    indices: list[IndexQuoteOut]
    northbound_net_yi: float | None
    advancers: int | None
    decliners: int | None
    source: str
    data_status: Literal["live", "mock", "unavailable"] = "live"
    message: str | None = None
    updated_at: datetime


class ProviderStatusOut(BaseModel):
    domain: str
    primary: str
    fallback: str | None = None
    tertiary: str | None = None
    primary_count: int = 0
    fallback_count: int = 0
    tertiary_count: int = 0
    degraded: bool = False
    message: str | None = None
    updated_at: datetime | None = None
    layer: str = "L1"
    latency_ms: int | None = None
    is_cached: bool = False
    is_mock: bool = False
    degraded_reason: str | None = None
    confidence: Literal["verified", "single_source", "delayed", "cached", "conflict", "missing"] = (
        "single_source"
    )


class DataSourceDetailOut(BaseModel):
    domain: str
    label: str
    layer: str
    source: str
    fetched_at: datetime | None = None
    latency_ms: int | None = None
    is_cached: bool = False
    is_mock: bool = False
    degraded: bool = False
    degraded_reason: str | None = None
    confidence: Literal["verified", "single_source", "delayed", "cached", "conflict", "missing"] = (
        "single_source"
    )
    conflict_with: list[str] = Field(default_factory=list)
    status: Literal["ok", "degraded", "missing", "mock", "configured", "not_configured"] = "ok"


class ProviderMetaOut(BaseModel):
    key: str
    label: str
    layer: str
    provider: str
    domain: str
    default_ttl_seconds: int | None = None


class QuotePriceConflictOut(BaseModel):
    symbol: str
    name: str
    primary_source: str
    primary_price: float
    compare_source: str
    compare_price: float
    diff_pct: float


class DataSourceStatusOut(BaseModel):
    quotes: ProviderStatusOut | None = None
    overview: ProviderStatusOut | None = None
    details: list[DataSourceDetailOut] = Field(default_factory=list)
    provider_catalog: list[ProviderMetaOut] = Field(default_factory=list)
    use_mock: bool = False
    tushare_configured: bool = False
    tushare_available: bool = False
    tushare_status: Literal["no_token", "unavailable", "invalid", "ok", "quota"] = "no_token"
    price_conflicts: list[QuotePriceConflictOut] = Field(default_factory=list)


class ResearchReportListItem(BaseModel):
    id: int
    symbol: str
    name: str
    composite_score: float
    bias: str
    summary: str
    has_debate: bool
    created_at: datetime


class IndustryResearchRequest(BaseModel):
    sector: str = Field(min_length=1, max_length=50)
    query: str = Field(default="", max_length=500)
    enable_master_commentary: bool | None = None


class BriefingSection(BaseModel):
    title: str
    content: str


class BriefingGenerateRequest(BaseModel):
    reading_mode: Literal["friendly", "standard", "professional"] | None = None
    output_locale: Literal["zh", "en"] | None = None


class BriefingOut(BaseModel):
    kind: Literal["premarket", "intraday", "postmarket"]
    title: str
    sections: list[BriefingSection]
    summary: str
    disclaimer: str = DISCLAIMER
    generated_at: datetime


class BriefingRecordOut(BaseModel):
    id: int
    kind: Literal["premarket", "intraday", "postmarket"]
    title: str
    summary: str
    sections: list[BriefingSection]
    generated_at: datetime

    model_config = {"from_attributes": True}


class BriefingScheduleStatus(BaseModel):
    enabled: bool
    premarket_time: str = "09:05"
    intraday_time: str = "11:35"
    postmarket_time: str = "15:35"
    morning_time: str = "09:05"
    closing_time: str = "15:35"
    timezone: str = "Asia/Shanghai"


class SignalBacktestHorizon(BaseModel):
    days: int
    sample_count: int
    bullish_count: int
    bearish_count: int
    bullish_avg_return_pct: float | None = None
    bearish_avg_return_pct: float | None = None
    bullish_median_return_pct: float | None = None
    bearish_median_return_pct: float | None = None
    bullish_positive_rate_pct: float | None = None
    bearish_negative_rate_pct: float | None = None
    # 偏多均涨 − 偏空均涨：方向可分性（正值表示偏多事后更强）
    spread_avg_return_pct: float | None = None
    bias_bullish_avg_return_pct: float | None = None
    bias_bearish_avg_return_pct: float | None = None
    factor_tilt_bullish_avg_return_pct: float | None = None
    factor_tilt_bearish_avg_return_pct: float | None = None


class SignalBacktestOut(BaseModel):
    """Research-signal verification stats (not a strategy backtester)."""

    horizons: list[SignalBacktestHorizon]
    disclaimer: str
    label: str = "研究信号验证"
    notes: list[str] = Field(default_factory=list)
    sample_bias_note: str = "样本来自本机历史研报，存在选择偏差；未计入交易成本与冲击成本。"
    unique_symbols: int = 0
    bias_sample_count: int = 0
    factor_tilt_sample_count: int = 0
    point_in_time: bool = True
    pit_note: str = (
        "点-in-time：验证仅使用报告落库时保存的 bias/factors 快照 + 之后的前复权日线；"
        "不重拉事后财务。"
    )


class ReportPostHocHorizon(BaseModel):
    days: int
    return_pct: float | None = None
    partial: bool = False
    note: str | None = None
    bars_adjust: str | None = None
    bars_source: str | None = None


class ReportPostHocOut(BaseModel):
    report_id: int
    symbol: str
    horizons: list[ReportPostHocHorizon]
    disclaimer: str = DISCLAIMER
    label: str = "单报告事后核对"
    point_in_time: bool = True
    signal_as_of: str | None = None
    pit_note: str = "点-in-time：信号时点为报告创建日；收益仅用创建日及之后的前复权收盘价。"


class ResearchTimelineFactorSnap(BaseModel):
    key: str
    label: str
    value: float | None = None
    percentile: float | None = None
    partial: bool = False


class ResearchTimelineEntryOut(BaseModel):
    report_id: int
    created_at: datetime
    bias: str
    composite_score: float
    analysis_depth: str = "standard"
    summary: str = ""
    factor_alignment_note: str | None = None
    factors: list[ResearchTimelineFactorSnap] = Field(default_factory=list)
    post_hoc: list[ReportPostHocHorizon] = Field(default_factory=list)
    bias_changed: bool = False
    score_delta: float | None = None
    thesis_claim: str | None = None


class ResearchTimelineOut(BaseModel):
    symbol: str
    name: str
    entries: list[ResearchTimelineEntryOut] = Field(default_factory=list)
    point_in_time: bool = True
    notes: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


class CompareRowOut(BaseModel):
    symbol: str
    name: str
    factors: list[NumericFactorOut] = Field(default_factory=list)
    bars_adjust: str = "none"
    bars_source: str = ""
    bars_as_of: str | None = None
    partial: bool = False
    note: str | None = None


class CompareTableOut(BaseModel):
    rows: list[CompareRowOut]
    as_of: str
    point_in_time: bool = True
    notes: list[str] = Field(default_factory=list)


class CompareRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, max_length=12)


class EventStudyWindowOut(BaseModel):
    days: int
    sample_count: int
    avg_return_pct: float | None = None
    positive_rate_pct: float | None = None


class EventStudyEventOut(BaseModel):
    title: str
    event_kind: str
    event_date: str
    returns: dict[str, float | None] = Field(default_factory=dict)
    partial: bool = False
    note: str | None = None
    url: str | None = None


class EventStudyOut(BaseModel):
    symbol: str
    name: str
    event_filter: str
    events: list[EventStudyEventOut]
    windows: list[EventStudyWindowOut]
    kind_counts: dict[str, int] = Field(default_factory=dict)
    bars_adjust: str = "none"
    bars_source: str = ""
    notes: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER
    as_of: str | None = None
    point_in_time: bool = True


class EventStudyBatchRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, max_length=8)
    event_filter: Literal["earnings", "risk", "all"] = "earnings"


class EventStudyBatchOut(BaseModel):
    items: list[EventStudyOut] = Field(default_factory=list)
    event_filter: str = "earnings"
    as_of: str | None = None
    notes: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


class HypothesisWindowOut(BaseModel):
    days: int
    sample_count: int
    avg_return_pct: float | None = None
    hit_rate_pct: float | None = None


class HypothesisVerifyOut(BaseModel):
    symbol: str
    name: str
    rule: str
    rule_label: str
    windows: list[HypothesisWindowOut]
    sample_count: int = 0
    bars_adjust: str = "none"
    bars_source: str = ""
    point_in_time: bool = True
    as_of: str | None = None
    notes: list[str] = Field(default_factory=list)
    partial: bool = False
    disclaimer: str = DISCLAIMER


class HypothesisVerifyRequest(BaseModel):
    symbol: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    rule: str = "momentum_positive"
    lookback_days: int = Field(default=240, ge=60, le=800)


class BatchResearchRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, max_length=8)
    analysis_depth: Literal["standard", "comprehensive", "deep"] = "standard"
    with_debate: bool = False


class RefillGapsRequest(BaseModel):
    symbol: str = Field(pattern=r"^\d{6}$")
    gaps: list[str] = Field(default_factory=list, max_length=10)
    analysis_depth: Literal["standard", "comprehensive", "deep"] | None = None


class BatchResearchItemOut(BaseModel):
    symbol: str
    name: str
    report: ResearchReportOut | None = None
    error: str | None = None
    partial: bool = False


class BatchResearchOut(BaseModel):
    items: list[BatchResearchItemOut]
    as_of: str
    notes: list[str] = Field(default_factory=list)


class MemorySearchHit(BaseModel):
    report_id: int
    symbol: str
    name: str
    bias: str
    summary: str
    composite_score: float
    created_at: datetime


class MemorySearchOut(BaseModel):
    query: str
    hits: list[MemorySearchHit]


class StreamCheckpointOut(BaseModel):
    session_id: str
    checkpoint: dict[str, object] | None = None


class LlmUsageOut(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str | None = None
    estimated_cost_cny: float | None = None
    is_estimate: bool = False
    llm_calls: int = 0


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    cards: list[CardPayload]
    intent: str
    partial: bool = False
    follow_up_questions: list[str] = Field(default_factory=list, max_length=4)
    disclaimer: str = DISCLAIMER
    llm_usage: LlmUsageOut | None = None


# ── News Deep Analysis ──────────────────────────────────


class NewsAnalysisStockImpact(BaseModel):
    symbol: str
    name: str
    price: float
    change_pct: float
    pe_ttm: float | None = None
    technical_signal: str = "neutral"  # bullish / bearish / neutral
    technical_summary: str = ""
    fundamental_summary: str = ""
    sentiment_summary: str = ""
    impact_assessment: str = ""
    impact_direction: Literal["positive", "negative", "neutral"] = "neutral"
    key_points: list[str] = Field(default_factory=list)


class NewsAnalysisOut(BaseModel):
    news_id: int
    title: str
    summary: str
    source: str
    entities: list[str]
    related_stocks: list[NewsAnalysisStockImpact]
    market_context: str = ""
    cross_analysis: str = ""
    overall_assessment: str = ""
    disclaimer: str = DISCLAIMER


# ── Daily Action Center ──────────────────────────────────


class ActionSignal(BaseModel):
    type: Literal["price", "news", "risk", "fundamental", "market", "research"] = "fundamental"
    severity: Literal["critical", "warning", "info"] = "info"
    title: str
    detail: str = ""
    action: str = ""
    action_target: str = ""
    symbol: str | None = None
    weight: int = 0


class DailyActionCenterOut(BaseModel):
    signals: list[ActionSignal] = Field(default_factory=list)
    summary: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    disclaimer: str = DISCLAIMER


# ── Advisor Asset Allocation ───────────────────────────


class AssetAllocationRequest(BaseModel):
    """投顾模式专属：根据风险等级 + 现金流给出资产配置参考。"""

    risk_tolerance: Literal["conservative", "moderate", "aggressive"]
    monthly_income: float | None = Field(
        default=None, gt=0, description="月收入（元），用于现金流换算"
    )
    reading_mode: Literal["friendly", "standard", "professional"] | None = None
    output_locale: Literal["zh", "en"] | None = None


class AssetAllocationOut(BaseModel):
    risk_tolerance: Literal["conservative", "moderate", "aggressive"]
    risk_label: str = Field(description="风险等级中文标签：保守/稳健/进取")
    allocation: dict[str, float] = Field(
        description='参考配置比例，如 {"股票": 0.5, "债券": 0.35, "现金": 0.15}'
    )
    rationale: str = Field(description="为什么这样配置的解释（投顾模式用大白话）")
    cash_flow_impact: str | None = Field(default=None, description="现金流影响分析（有月收入时）")
    emergency_fund_note: str | None = Field(default=None, description="应急资金建议（有月收入时）")
    disclaimer: str = DISCLAIMER


class AllocationDeviationRequest(BaseModel):
    """Expert-mode sector targets (fractions or percents). Display only."""

    targets: dict[str, float] = Field(default_factory=dict, max_length=30)


class AllocationDeviationRow(BaseModel):
    sector: str
    actual: float
    target: float
    delta: float


class AllocationDeviationOut(BaseModel):
    actual: dict[str, float] = Field(default_factory=dict)
    targets: dict[str, float] = Field(default_factory=dict)
    rows: list[AllocationDeviationRow] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


# ── Sector movers ──────────────────────────────────────


class SectorBoardOut(BaseModel):
    code: str
    name: str
    change_pct: float
    leader_name: str
    leader_symbol: str
    leader_change_pct: float


class SectorMoversOut(BaseModel):
    gainers: list[SectorBoardOut] = Field(default_factory=list)
    losers: list[SectorBoardOut] = Field(default_factory=list)
    boards: list[SectorBoardOut] | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    disclaimer: str = DISCLAIMER


# ── Price alerts ───────────────────────────────────────


class PriceAlertSettingsOut(BaseModel):
    enabled: bool
    threshold_pct: float


class PriceAlertSettingsUpdate(BaseModel):
    enabled: bool | None = None
    threshold_pct: float | None = Field(default=None, ge=0.5, le=20)


class PriceAlertNotificationOut(BaseModel):
    id: int
    symbol: str
    name: str
    change_pct: float
    threshold_pct: float
    trading_date: date
    message: str
    read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SentimentDriverOut(BaseModel):
    label: str
    value: str
    impact: str


class SentimentOut(BaseModel):
    score: int
    label: str
    drivers: list[SentimentDriverOut]
    source: str
