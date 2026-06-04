"""Market-wide research context (no single stock symbol)."""

from dataclasses import dataclass

from stockresearch.core.schemas import MarketOverviewOut
from stockresearch.utils.llm import LLMClient

MARKET_SYMBOL = "MARKET"
MARKET_NAME = "A股市场"


@dataclass
class MarketResearchContext:
    query: str
    llm: LLMClient
    overview: MarketOverviewOut
    overview_text: str
