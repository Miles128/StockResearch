"""Pydantic schemas for API and agents."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from invesbao.core.constants import DISCLAIMER


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

    @model_validator(mode="after")
    def require_identifier_and_quantity(self) -> "HoldingCreate":
        if not (self.query or self.symbol or self.name):
            raise ValueError("请提供股票代码或名称（query / symbol / name 三选一）")
        if self.lots is None and self.quantity is None:
            raise ValueError("请提供持仓手数 lots")
        if self.lots is not None:
            object.__setattr__(self, "quantity", self.lots * 100)
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


class HoldingOut(BaseModel):
    id: int
    symbol: str
    name: str
    cost_price: float
    quantity: int
    sector: str

    model_config = {"from_attributes": True}


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


class RiskCheckupOut(BaseModel):
    alerts: list[RiskAlertOut]
    portfolio_summary: str
    llm_analysis: LLMRiskAnalysis | None = None
    disclaimer: str = DISCLAIMER


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


class CardPayload(BaseModel):
    type: Literal["news", "research", "risk", "text", "market"]
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


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    cards: list[CardPayload]
    intent: str
    disclaimer: str = DISCLAIMER
    partial: bool = False
