"""Market data providers package — split from the legacy single market.py.

Re-exports keep `from stockresearch.data.providers.market import X` working.
"""

from stockresearch.data.providers.market.chips import ChipsDataProvider
from stockresearch.data.providers.market.common import (
    Quote,
    _as_datetime,
    _as_float,
    _market_code,
    _mock_quote,
    _quote_from_cache,
    _quote_to_cache,
    _use_mock_market_data,
)
from stockresearch.data.providers.market.financial import FinancialDataProvider
from stockresearch.data.providers.market.quotes import QuoteProvider
from stockresearch.data.providers.market.rules import MarketRuleProvider
from stockresearch.data.providers.market.sentiment import (
    SentimentDataProvider,
    _fetch_xueqiu_hot_sync,
    _lookup_xueqiu_row,
)
from stockresearch.data.providers.market.technical import TechnicalDataProvider

__all__ = [
    "ChipsDataProvider",
    "FinancialDataProvider",
    "MarketRuleProvider",
    "Quote",
    "QuoteProvider",
    "SentimentDataProvider",
    "TechnicalDataProvider",
    "_as_datetime",
    "_as_float",
    "_fetch_xueqiu_hot_sync",
    "_lookup_xueqiu_row",
    "_market_code",
    "_mock_quote",
    "_quote_from_cache",
    "_quote_to_cache",
    "_use_mock_market_data",
]
