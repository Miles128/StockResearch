"""Holdings and watchlist routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from invesbao.api.deps import get_current_user, handle_invesbao_error
from invesbao.core.exceptions import ValidationError
from invesbao.core.schemas import (
    HoldingConfirmCreate,
    HoldingCreate,
    HoldingOut,
    SectorBackfillOut,
    StockCandidateOut,
    StockLookupOut,
    StockLookupRequest,
    WatchlistCreate,
    WatchlistOut,
)
from invesbao.db.models import Holding, User, WatchlistItem
from invesbao.db.session import get_db
from invesbao.services.stock_lookup import lookup_stock
from invesbao.services.stock_sector import backfill_holding_sectors, resolve_stock_sector
from invesbao.utils.llm import get_llm_client
from invesbao.services.symbol_resolver import resolve_stock_query

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

LOTS_SIZE = 100


def _upsert_holding(
    db: Session,
    *,
    user_id: int,
    symbol: str,
    name: str,
    cost_price: float,
    quantity: int,
    sector: str | None = None,
) -> Holding:
    existing = (
        db.query(Holding)
        .filter(Holding.user_id == user_id, Holding.symbol == symbol)
        .first()
    )
    if existing is not None:
        total_qty = existing.quantity + quantity
        existing.cost_price = (
            existing.cost_price * existing.quantity + cost_price * quantity
        ) / total_qty
        existing.quantity = total_qty
        existing.name = name
        if sector:
            existing.sector = sector
        db.commit()
        db.refresh(existing)
        return existing

    holding = Holding(
        user_id=user_id,
        symbol=symbol,
        name=name,
        cost_price=cost_price,
        quantity=quantity,
        sector=sector or "未知",
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


def _resolve_holding(payload: HoldingCreate) -> tuple[str, str]:
    if payload.symbol and payload.name:
        return payload.symbol, payload.name
    if payload.symbol and not payload.name:
        _, name = resolve_stock_query(payload.symbol)
        return payload.symbol, name
    if payload.query:
        return resolve_stock_query(payload.query)
    if payload.name and not payload.symbol:
        return resolve_stock_query(payload.name)
    raise ValidationError("请提供股票代码或名称")


@router.post("/holdings/lookup", response_model=StockLookupOut)
async def lookup_holding_symbol(payload: StockLookupRequest) -> StockLookupOut:
    result = await lookup_stock(payload.query, llm=get_llm_client())
    sector: str | None = None
    if result.status == "confirmed" and result.symbol and result.name:
        sector = await resolve_stock_sector(result.symbol, result.name)
    return StockLookupOut(
        status=result.status,  # type: ignore[arg-type]
        symbol=result.symbol,
        name=result.name,
        sector=sector,
        message=result.message,
        candidates=[StockCandidateOut(symbol=c.symbol, name=c.name) for c in result.candidates],
        normalized_query=result.normalized_query,
    )


@router.get("/holdings", response_model=list[HoldingOut])
def list_holdings(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Holding]:
    return db.query(Holding).filter(Holding.user_id == user.id).all()


@router.post("/holdings", response_model=HoldingOut)
async def create_holding(
    payload: HoldingCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Holding:
    try:
        if payload.symbol and payload.name:
            symbol, name = payload.symbol, payload.name
        elif payload.query:
            lookup = await lookup_stock(payload.query, llm=get_llm_client())
            if lookup.status != "confirmed" or not lookup.symbol or not lookup.name:
                raise ValidationError(lookup.message)
            symbol, name = lookup.symbol, lookup.name
        else:
            symbol, name = _resolve_holding(payload)
    except ValidationError as exc:
        raise handle_invesbao_error(exc) from exc

    if payload.quantity is None:
        raise HTTPException(status_code=422, detail="请提供持仓手数")

    sector = payload.sector
    if not sector or sector == "未知":
        sector = await resolve_stock_sector(symbol, name)

    return _upsert_holding(
        db,
        user_id=user.id,
        symbol=symbol,
        name=name,
        cost_price=payload.cost_price,
        quantity=payload.quantity,
        sector=sector,
    )


@router.post("/holdings/confirm", response_model=HoldingOut)
async def confirm_holding(
    payload: HoldingConfirmCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Holding:
    sector = payload.sector
    if not sector or sector == "未知":
        sector = await resolve_stock_sector(payload.symbol, payload.name)
    return _upsert_holding(
        db,
        user_id=user.id,
        symbol=payload.symbol,
        name=payload.name,
        cost_price=payload.cost_price,
        quantity=payload.lots * LOTS_SIZE,
        sector=sector,
    )


@router.post("/holdings/backfill-sectors", response_model=SectorBackfillOut)
async def backfill_sectors(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectorBackfillOut:
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    updated, skipped = await backfill_holding_sectors(holdings)
    if updated:
        db.commit()
    if updated == 0 and not any(not h.sector or h.sector == "未知" for h in holdings):
        message = "所有持仓已有行业，无需补全"
    elif updated == 0:
        message = "未能识别行业，请稍后重试"
    else:
        message = f"已补全 {updated} 只持仓的行业"
    return SectorBackfillOut(updated=updated, skipped=skipped, message=message)


@router.delete("/holdings/{holding_id}")
def delete_holding(
    holding_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    holding = db.query(Holding).filter(Holding.id == holding_id, Holding.user_id == user.id).first()
    if holding is None:
        raise HTTPException(status_code=404, detail="Holding not found")
    db.delete(holding)
    db.commit()
    return {"status": "deleted"}


@router.get("/watchlist", response_model=list[WatchlistOut])
def list_watchlist(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[WatchlistItem]:
    return db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).all()


@router.post("/watchlist", response_model=WatchlistOut)
def add_watchlist(
    payload: WatchlistCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WatchlistItem:
    item = WatchlistItem(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
