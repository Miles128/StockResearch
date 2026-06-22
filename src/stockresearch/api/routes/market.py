"""Market data routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.core.config import get_settings
from stockresearch.core.data_source_config import get_tushare_token
from stockresearch.core.schemas import (
    DataSourceStatusOut,
    KlineChartOut,
    MarketOverviewOut,
    ProviderStatusOut,
    StockQuoteOut,
)
from stockresearch.data.providers.market import TechnicalDataProvider
from stockresearch.data.providers.market_overview import BatchQuoteProvider, MarketOverviewProvider
from stockresearch.data.registry import get_snapshots
from stockresearch.db.models import Holding, User
from stockresearch.db.session import get_db

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/overview", response_model=MarketOverviewOut)
async def market_overview(
    _user: User = Depends(get_current_user),
) -> MarketOverviewOut:
    return await MarketOverviewProvider().get_overview()


@router.get("/quotes", response_model=list[StockQuoteOut])
async def stock_quotes(
    symbols: str = Query(default="", description="Comma-separated symbols, e.g. 600519,300750"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StockQuoteOut]:
    symbol_list = list(dict.fromkeys(s.strip() for s in symbols.split(",") if s.strip()))
    if not symbol_list:
        holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
        symbol_list = list(dict.fromkeys(h.symbol for h in holdings))
    if not symbol_list:
        return []
    return await BatchQuoteProvider().get_quotes(symbol_list)


@router.get("/kline", response_model=KlineChartOut)
async def stock_kline(
    symbol: str = Query(min_length=6, max_length=6, pattern=r"^\d{6}$"),
    days: int = Query(default=60, ge=10, le=250),
    _user: User = Depends(get_current_user),
) -> KlineChartOut:
    raw = await TechnicalDataProvider().get_kline_chart(symbol, days)
    return KlineChartOut.model_validate(raw)


@router.get("/data-status", response_model=DataSourceStatusOut)
async def data_source_status(
    _user: User = Depends(get_current_user),
) -> DataSourceStatusOut:
    snapshots = get_snapshots()
    quotes = snapshots.get("quotes")
    overview = snapshots.get("overview")
    return DataSourceStatusOut(
        quotes=ProviderStatusOut(
            domain=quotes.domain,
            primary=quotes.primary,
            fallback=quotes.fallback,
            primary_count=quotes.primary_count,
            fallback_count=quotes.fallback_count,
            degraded=quotes.degraded,
            message=quotes.message,
            updated_at=quotes.updated_at,
        )
        if quotes
        else None,
        overview=ProviderStatusOut(
            domain=overview.domain,
            primary=overview.primary,
            fallback=overview.fallback,
            primary_count=overview.primary_count,
            fallback_count=overview.fallback_count,
            degraded=overview.degraded,
            message=overview.message,
            updated_at=overview.updated_at,
        )
        if overview
        else None,
        use_mock=get_settings().use_mock_market_data,
        tushare_configured=bool(get_tushare_token()),
        tushare_available=_tushare_runtime_available(),
    )


def _tushare_runtime_available() -> bool:
    try:
        import tushare  # noqa: F401
    except ImportError:
        return False
    return True
