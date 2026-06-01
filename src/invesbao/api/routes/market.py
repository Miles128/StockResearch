"""Market data routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from invesbao.api.deps import get_current_user
from invesbao.core.schemas import MarketOverviewOut, StockQuoteOut
from invesbao.data.providers.market_overview import BatchQuoteProvider, MarketOverviewProvider
from invesbao.db.models import Holding, User
from invesbao.db.session import get_db

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
