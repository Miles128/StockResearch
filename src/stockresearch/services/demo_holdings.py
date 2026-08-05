"""Demo holdings — zero-barrier onboarding with pre-loaded sample portfolio."""

from typing import Any

from sqlalchemy.orm import Session

from stockresearch.db.models import Holding

DEMO_HOLDINGS: list[dict[str, Any]] = [
    {"symbol": "600519", "name": "贵州茅台", "cost_price": 1680.0, "lots": 2, "sector": "白酒"},
    {"symbol": "300750", "name": "宁德时代", "cost_price": 195.0, "lots": 5, "sector": "新能源"},
    {"symbol": "600036", "name": "招商银行", "cost_price": 35.0, "lots": 10, "sector": "银行"},
]


def load_demo_holdings(db: Session, user_id: int) -> list[Holding]:
    """Insert demo holdings for the user. Skips if user already has holdings."""
    existing = db.query(Holding).filter(Holding.user_id == user_id).count()
    if existing > 0:
        return db.query(Holding).filter(Holding.user_id == user_id).all()

    for demo in DEMO_HOLDINGS:
        db.add(
            Holding(
                user_id=user_id,
                symbol=demo["symbol"],
                name=demo["name"],
                cost_price=demo["cost_price"],
                quantity=demo["lots"] * 100,
                sector=demo["sector"],
            )
        )
    db.commit()
    return db.query(Holding).filter(Holding.user_id == user_id).all()


def clear_demo_holdings(db: Session, user_id: int) -> int:
    """Remove all demo holdings. Returns count deleted."""
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    count = len(holdings)
    for h in holdings:
        db.delete(h)
    db.commit()
    return count


def is_demo_mode(db: Session, user_id: int) -> bool:
    """Check if current holdings are demo (all 3 demo symbols present, no others)."""
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    demo_symbols = {d["symbol"] for d in DEMO_HOLDINGS}
    holding_symbols = {h.symbol for h in holdings}
    return holding_symbols == demo_symbols and len(holdings) == len(DEMO_HOLDINGS)
