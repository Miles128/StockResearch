"""持仓与交易台账核心业务逻辑（从 API 路由层下沉，脱离 HTTP 可复用/可测）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from stockresearch.core.exceptions import ValidationError
from stockresearch.core.schemas import HoldingCreate, HoldingTransactionItem
from stockresearch.db.models import Holding, ResearchReport, Trade
from stockresearch.services.stock_lookup import lookup_stock
from stockresearch.services.stock_sector import resolve_stock_sector
from stockresearch.services.symbol_resolver import resolve_stock_query
from stockresearch.utils.llm import get_llm_client

LOTS_SIZE = 100


def latest_report_id(db: Session, user_id: int, symbol: str) -> int | None:
    """Attach the most recent research report for the symbol (decision journal)."""
    report = (
        db.query(ResearchReport)
        .filter(
            ResearchReport.symbol == symbol,
            (ResearchReport.user_id == user_id) | (ResearchReport.user_id.is_(None)),
        )
        .order_by(ResearchReport.created_at.desc(), ResearchReport.id.desc())
        .first()
    )
    return report.id if report else None


def record_trade(
    db: Session,
    *,
    user_id: int,
    symbol: str,
    name: str,
    side: str,
    price: float,
    quantity: int,
    trade_date: date | None = None,
    realized_pnl: float | None = None,
    note: str | None = None,
    commit: bool = False,
) -> Trade:
    trade = Trade(
        user_id=user_id,
        symbol=symbol,
        name=name,
        side=side,
        price=price,
        quantity=quantity,
        trade_date=trade_date,
        realized_pnl=None if realized_pnl is None else round(realized_pnl, 2),
        note=(note.strip() or None) if note else None,
        report_id=latest_report_id(db, user_id, symbol),
    )
    db.add(trade)
    if commit:
        db.commit()
    else:
        db.flush()
    return trade


def upsert_holding(
    db: Session,
    *,
    user_id: int,
    symbol: str,
    name: str,
    cost_price: float,
    quantity: int,
    sector: str | None = None,
    buy_date: date | None = None,
    commit: bool = True,
) -> Holding:
    existing = (
        db.query(Holding).filter(Holding.user_id == user_id, Holding.symbol == symbol).first()
    )
    if existing is not None:
        total_qty = existing.quantity + quantity
        existing.cost_price = Decimal(
            (float(existing.cost_price) * existing.quantity + cost_price * quantity) / total_qty
        )
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


def sell_holding(
    db: Session,
    *,
    user_id: int,
    symbol: str,
    quantity: int,
    name: str | None = None,
    commit: bool = True,
) -> None:
    holding = db.query(Holding).filter(Holding.user_id == user_id, Holding.symbol == symbol).first()
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


async def resolve_transaction_symbol_name(
    item: HoldingTransactionItem,
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
    sector = await resolve_stock_sector(lookup.symbol, lookup.name)
    return lookup.symbol, lookup.name, sector


def resolve_holding(payload: HoldingCreate) -> tuple[str, str]:
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
