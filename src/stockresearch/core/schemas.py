"""Pydantic schemas for API and agents."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from stockresearch.core.constants import DISCLAIMER
from stockresearch.services.trading_calendar import validate_buy_date


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


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


class NewsIngestOut(BaseModel):
    inserted: int
    scanned: int
    skipped: int
    purged: int
    message: str


class DimensionResult(BaseModel):
    agent: str
    score: float = Field(ge=1, le=10)
    confidence: Literal["high", "medium", "low"]
    highlights: list[str]
    risks: list[str]
    data_sources: list[str]


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


class ResearchReportOut(BaseModel):
    symbol: str
    name: str
    dimensions: dict[str, DimensionResult]
    composite_score: float
    composite_confidence: Literal["high", "medium", "low"]
    bias: Literal["bullish", "bearish", "neutral"]
    summary: str
    debate: DebateResult | None = None
    disclaimer: str = DISCLAIMER
    cached: bool = False


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


class RiskCheckupOut(BaseModel):
    alerts: list[RiskAlertOut]
    portfolio_summary: str
    llm_analysis: LLMRiskAnalysis | None = None
    metrics: PortfolioMetricsOut | None = None
    var_result: VaRResultOut | None = None
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
    default_temperature: float
    server_use_mock: bool


class LlmTestOut(BaseModel):
    ok: bool
    message: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    llm: LlmUserSettings | None = None
    analysis_mode: Literal["simple", "complex"] | None = None
    enable_debate: bool | None = None
    confirmed_symbol: str | None = Field(
        default=None, min_length=6, max_length=6, pattern=r"^\d{6}$"
    )
    confirmed_name: str | None = Field(default=None, min_length=1, max_length=50)


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


class StockQuoteOut(BaseModel):
    symbol: str
    name: str
    price: float
    change_pct: float
    high: float
    low: float
    volume: float
    sector: str = "未知"
    source: str = "live"


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
    primary_count: int = 0
    fallback_count: int = 0
    degraded: bool = False
    message: str | None = None
    updated_at: datetime | None = None


class DataSourceStatusOut(BaseModel):
    quotes: ProviderStatusOut | None = None
    overview: ProviderStatusOut | None = None
    use_mock: bool = False
    tushare_configured: bool = False
    tushare_available: bool = False


class ResearchReportListItem(BaseModel):
    id: int
    symbol: str
    name: str
    composite_score: float
    bias: str
    summary: str
    has_debate: bool
    created_at: datetime


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    cards: list[CardPayload]
    intent: str
    disclaimer: str = DISCLAIMER
    partial: bool = False
