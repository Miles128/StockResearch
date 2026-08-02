"""Holdings and watchlist routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user, handle_stockresearch_error
from stockresearch.core.exceptions import ValidationError
from stockresearch.core.schemas import (
    AllocationDeviationOut,
    AllocationDeviationRequest,
    HoldingConfirmCreate,
    HoldingCreate,
    HoldingEnrichedOut,
    HoldingOut,
    HoldingTransactionBatch,
    HoldingTransactionResult,
    SectorBackfillOut,
    StockCandidateOut,
    StockLookupOut,
    StockLookupRequest,
    StockQuoteOut,
    WatchlistCreate,
    WatchlistOut,
)
from stockresearch.data.providers.market_overview import BatchQuoteProvider
from stockresearch.db.models import Holding, User, WatchlistItem
from stockresearch.db.session import get_db
from stockresearch.services.allocation_deviation import build_allocation_deviation
from stockresearch.services.provider_cache_policy import quote_cache_ttl_seconds
from stockresearch.services.user_preferences import get_mode_settings
from stockresearch.services.holding_metrics import (
    annualized_return_pct,
    profit_amount,
    profit_pct,
)
from stockresearch.services.market_session import (
    MarketSession,
    a_share_market_session,
    price_label_for_session,
)
from stockresearch.services.stock_lookup import lookup_stock
from stockresearch.services.stock_sector import backfill_holding_sectors, resolve_stock_sector
from stockresearch.services.symbol_resolver import resolve_stock_query
from stockresearch.utils.llm import get_llm_client

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
    buy_date=None,
    commit: bool = True,
) -> Holding:
    existing = (
        db.query(Holding)
        .filter(Holding.user_id == user_id, Holding.symbol == symbol)
        .first()
    )
    if existing is not None:
        total_qty = existing.quantity + quantity
        existing.cost_price = (
            float(existing.cost_price) * existing.quantity + cost_price * quantity
        ) / total_qty
        existing.quantity = total_qty
        existing.name = name
        if sector:
            existing.sector = sector
        if commit:
            db.commit()
            db.refresh(existing)
        else:
            db.flush()
        return existing

    holding = Holding(
        user_id=user_id,
        symbol=symbol,
        name=name,
        cost_price=cost_price,
        quantity=quantity,
        sector=sector or "未知",
        buy_date=buy_date,
    )
    db.add(holding)
    if commit:
        db.commit()
        db.refresh(holding)
    else:
        db.flush()
    return holding


def _sell_holding(
    db: Session,
    *,
    user_id: int,
    symbol: str,
    quantity: int,
    name: str | None = None,
    commit: bool = True,
) -> None:
    holding = (
        db.query(Holding)
        .filter(Holding.user_id == user_id, Holding.symbol == symbol)
        .first()
    )
    label = name or (holding.name if holding else symbol)
    if holding is None or holding.quantity < quantity:
        available = holding.quantity if holding else 0
        raise ValidationError(f"{label} 卖出数量超出持仓（当前 {available} 股）")
    holding.quantity -= quantity
    if holding.quantity == 0:
        db.delete(holding)
    if commit:
        db.commit()
    else:
        db.flush()


async def _resolve_transaction_symbol_name(
    item,
) -> tuple[str, str, str | None]:
    if item.symbol and item.name:
        sector = await resolve_stock_sector(item.symbol, item.name)
        return item.symbol, item.name, sector
    if item.symbol and not item.name:
        _, name = resolve_stock_query(item.symbol)
        sector = await resolve_stock_sector(item.symbol, name)
        return item.symbol, name, sector
    query = item.query or item.name
    if not query:
        raise ValidationError("请提供股票代码或名称")
    lookup = await lookup_stock(query, llm=get_llm_client())
    if lookup.status != "confirmed" or not lookup.symbol or not lookup.name:
        raise ValidationError(lookup.message or f"无法识别股票：{query}")
    sector = lookup.sector or await resolve_stock_sector(lookup.symbol, lookup.name)
    return lookup.symbol, lookup.name, sector


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


def _enrich_holding(
    holding: Holding,
    quote_by_symbol: dict[str, StockQuoteOut],
    session: MarketSession,
) -> HoldingEnrichedOut:
    label = price_label_for_session(session)
    base = HoldingOut.model_validate(holding)
    q = quote_by_symbol.get(holding.symbol)
    if q is None:
        return HoldingEnrichedOut(
            **base.model_dump(),
            price_label=label,
            market_session=session,
            quote_available=False,
        )
    return HoldingEnrichedOut(
        **base.model_dump(),
        price=q.price,
        change_pct=q.change_pct,
        open=q.open,
        price_label=label,
        market_session=session,
        profit_amount=profit_amount(holding.float_cost_price, holding.quantity, q.price),
        profit_pct=profit_pct(holding.float_cost_price, q.price),
        annualized_pct=annualized_return_pct(holding.float_cost_price, q.price, holding.buy_date),
        quote_available=True,
    )


@router.get("/holdings/enriched", response_model=list[HoldingEnrichedOut])
async def list_holdings_enriched(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    force_refresh: bool = Query(default=False, description="Bypass quote cache for live refresh"),
) -> list[HoldingEnrichedOut]:
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    if not holdings:
        return []
    session = a_share_market_session()
    mode = get_mode_settings(db, user.id)
    ttl = quote_cache_ttl_seconds(mode)
    quotes = await BatchQuoteProvider().get_quotes(
        [h.symbol for h in holdings],
        include_sector=False,
        cache_ttl_seconds=ttl,
        force_refresh=force_refresh,
    )
    quote_map = {q.symbol: q for q in quotes}
    return [_enrich_holding(h, quote_map, session) for h in holdings]


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
        raise handle_stockresearch_error(exc) from exc

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
        buy_date=payload.buy_date,
    )


@router.post("/holdings/transactions", response_model=HoldingTransactionResult)
async def apply_holding_transactions(
    payload: HoldingTransactionBatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HoldingTransactionResult:
    try:
        resolved: list[tuple] = []
        for item in payload.transactions:
            symbol, name, sector = await _resolve_transaction_symbol_name(item)
            resolved.append((item, symbol, name, sector))

        for item, symbol, name, sector in resolved:
            quantity = item.lots * LOTS_SIZE
            if item.side == "buy":
                assert item.cost_price is not None
                _upsert_holding(
                    db,
                    user_id=user.id,
                    symbol=symbol,
                    name=name,
                    cost_price=item.cost_price,
                    quantity=quantity,
                    sector=sector,
                    buy_date=item.trade_date,
                    commit=False,
                )
            else:
                _sell_holding(
                    db,
                    user_id=user.id,
                    symbol=symbol,
                    quantity=quantity,
                    name=name,
                    commit=False,
                )
        db.commit()
    except ValidationError as exc:
        db.rollback()
        raise handle_stockresearch_error(exc) from exc

    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    return HoldingTransactionResult(
        applied=len(payload.transactions),
        holdings=[HoldingOut.model_validate(h) for h in holdings],
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
        buy_date=payload.buy_date,
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


@router.post("/allocation/deviation", response_model=AllocationDeviationOut)
def allocation_deviation(
    payload: AllocationDeviationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AllocationDeviationOut:
    """Expert-mode: sector target vs actual weights (display only)."""
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    return build_allocation_deviation(holdings, payload.targets)


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
    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user.id, WatchlistItem.symbol == payload.symbol)
        .first()
    )
    if existing:
        return existing
    item = WatchlistItem(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/watchlist/{item_id}")
def delete_watchlist(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id, WatchlistItem.user_id == user.id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    db.delete(item)
    db.commit()
    return {"status": "deleted"}


# ── Demo holdings ────────────────────────────────────────

@router.post("/demo")
def load_demo(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    from stockresearch.services.demo_holdings import is_demo_mode, load_demo_holdings

    holdings = load_demo_holdings(db, user.id)
    return {"status": "loaded", "count": len(holdings), "demo": is_demo_mode(db, user.id)}


@router.delete("/demo")
def clear_demo(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    from stockresearch.services.demo_holdings import clear_demo_holdings

    deleted = clear_demo_holdings(db, user.id)
    return {"status": "cleared", "deleted": deleted}


@router.get("/demo/status")
def demo_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    from stockresearch.services.demo_holdings import is_demo_mode

    return {"demo": is_demo_mode(db, user.id)}
