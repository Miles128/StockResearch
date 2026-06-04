"""User news interest profile: holdings, watchlist, and followed sectors."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from stockresearch.core.constants import AVAILABLE_SECTORS
from stockresearch.db.models import Holding, NewsItem, UserSectorPreference, WatchlistItem

_MARKET_KEYWORDS = (
    "央行",
    "国务院",
    "证监会",
    "A股",
    "沪指",
    "深成指",
    "创业板",
    "北向",
    "大盘",
    "两市",
    "流动性",
    "逆回购",
    "上证",
    "沪深",
)

MARKET_KEYWORDS = _MARKET_KEYWORDS


@dataclass(frozen=True)
class UserNewsInterests:
    symbols: tuple[str, ...]
    names: tuple[str, ...]
    sectors: frozenset[str]


def load_user_news_interests(db: Session, user_id: int) -> UserNewsInterests:
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    watchlist = db.query(WatchlistItem).filter(WatchlistItem.user_id == user_id).all()
    prefs = db.query(UserSectorPreference).filter(UserSectorPreference.user_id == user_id).all()

    symbols = [h.symbol for h in holdings] + [w.symbol for w in watchlist]
    names = [h.name for h in holdings] + [w.name for w in watchlist]
    sectors = {p.sector for p in prefs}
    for holding in holdings:
        if holding.sector and holding.sector != "未知":
            sectors.add(holding.sector)

    return UserNewsInterests(
        symbols=tuple(dict.fromkeys(symbols)),
        names=tuple(dict.fromkeys(names)),
        sectors=frozenset(sectors),
    )


def list_user_sectors(db: Session, user_id: int) -> list[str]:
    rows = db.query(UserSectorPreference).filter(UserSectorPreference.user_id == user_id).all()
    return [row.sector for row in rows]


def save_user_sectors(db: Session, user_id: int, sectors: list[str]) -> list[str]:
    valid = [s for s in sectors if s in AVAILABLE_SECTORS]
    db.query(UserSectorPreference).filter(UserSectorPreference.user_id == user_id).delete()
    for sector in dict.fromkeys(valid):
        db.add(UserSectorPreference(user_id=user_id, sector=sector))
    db.commit()
    return valid


def is_market_news(item: NewsItem) -> bool:
    text = f"{item.title} {item.summary}"
    if any(keyword in text for keyword in _MARKET_KEYWORDS):
        return True
    return "market" in item.entities


def classify_news(item: NewsItem, interests: UserNewsInterests) -> str | None:
    """Return category if item matches user feed, else None to exclude."""
    if is_market_news(item):
        return "market"

    entity_set = set(item.entities)
    if interests.symbols and entity_set & set(interests.symbols):
        return "holding"

    text = f"{item.title} {item.summary}"
    for name in interests.names:
        if name and name in text:
            return "holding"

    if interests.sectors:
        if entity_set & interests.sectors:
            return "sector"
        for sector in interests.sectors:
            if sector in text:
                return "sector"

    return None


def is_related_to_user(item: NewsItem, interests: UserNewsInterests) -> bool:
    category = classify_news(item, interests)
    return category in ("holding", "sector")


def purge_irrelevant_news(db: Session, interests: UserNewsInterests) -> int:
    """Delete stored news that no longer matches the user's feed rules."""
    deleted = 0
    for item in db.query(NewsItem).all():
        if classify_news(item, interests) is None:
            db.delete(item)
            deleted += 1
    if deleted:
        db.commit()
    return deleted
