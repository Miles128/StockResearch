"""News processing pipeline: NER, dedup, sentiment, summary."""

import hashlib
from dataclasses import dataclass

from sqlalchemy.orm import Session

from stockresearch.agents.news.filter import filter_and_rank, layer1_blacklist_reject
from stockresearch.core.constants import (
    AVAILABLE_SECTORS,
    IMPACT_MAJOR,
    IMPACT_NOISE,
    IMPACT_NORMAL,
    SENTIMENT_BEARISH,
    SENTIMENT_BULLISH,
    SENTIMENT_NEUTRAL,
)
from stockresearch.data.providers.news import NewsProvider
from stockresearch.db.models import NewsItem
from stockresearch.services.news_interests import (
    MARKET_KEYWORDS,
    UserNewsInterests,
    classify_news,
)

_BULL_WORDS = ("利好", "增长", "突破", "回购", "分红", "净流入", "上调")
_BEAR_WORDS = ("利空", "下滑", "亏损", "问询", "立案", "减持", "净流出", "下调", "ST")


@dataclass(frozen=True)
class NewsIngestResult:
    inserted: int
    scanned: int
    skipped: int
    message: str


def content_hash(title: str, source: str) -> str:
    return hashlib.sha256(f"{source}:{title}".encode()).hexdigest()


def extract_entities(text: str) -> list[str]:
    entities: list[str] = []
    from stockresearch.utils.symbols import extract_symbols

    entities.extend(extract_symbols(text))
    for kw in AVAILABLE_SECTORS:
        if kw in text:
            entities.append(kw)
    if any(kw in text for kw in MARKET_KEYWORDS):
        entities.append("market")
    return list(dict.fromkeys(entities))


def score_sentiment(text: str) -> str:
    bull = sum(1 for w in _BULL_WORDS if w in text)
    bear = sum(1 for w in _BEAR_WORDS if w in text)
    if bull > bear + 1:
        return SENTIMENT_BULLISH
    if bear > bull + 1:
        return SENTIMENT_BEARISH
    return SENTIMENT_NEUTRAL


def score_impact(title: str, entities: list[str]) -> str:
    if layer1_blacklist_reject(title):
        return IMPACT_NOISE
    if any(kw in title for kw in ("央行", "国务院", "证监会", "重大", "立案", "退市")):
        return IMPACT_MAJOR
    if entities:
        return IMPACT_NORMAL
    return IMPACT_NOISE


def quick_summary(title: str, content: str) -> str:
    text = content.strip()
    if text:
        return text
    return title.strip()


class NewsPipeline:
    def __init__(self) -> None:
        self._provider = NewsProvider()

    async def ingest(
        self,
        db: Session,
        interests: UserNewsInterests,
        limit: int = 30,
    ) -> NewsIngestResult:
        symbol_pairs = list(zip(interests.symbols, interests.names, strict=False))
        raw_items = await self._provider.fetch_for_user(
            symbol_pairs,
            interests.sectors,
            limit=limit,
        )
        inserted = 0
        skipped = 0
        scanned = 0
        for raw in raw_items:
            scanned += 1
            if layer1_blacklist_reject(raw.title):
                skipped += 1
                continue
            h = content_hash(raw.title, raw.source)
            if db.query(NewsItem).filter(NewsItem.content_hash == h).first():
                skipped += 1
                continue
            text = f"{raw.title} {raw.content}"
            entities = extract_entities(text)
            sentiment = score_sentiment(text)
            impact = score_impact(raw.title, entities)
            summary = quick_summary(raw.title, raw.content)
            candidate = NewsItem(
                title=raw.title,
                content=raw.content,
                summary=summary,
                source=raw.source,
                sentiment=sentiment,
                impact_level=impact,
                entities=entities,
                content_hash=h,
                published_at=raw.published_at,
            )
            if classify_news(candidate, interests) is None:
                skipped += 1
                continue
            db.add(candidate)
            inserted += 1
            if inserted >= limit:
                break
        db.commit()
        message = (
            f"扫描 {scanned} 条，入库 {inserted} 条与你相关的快讯"
            if inserted
            else "未发现与你持仓/板块/大盘相关的新快讯"
        )
        return NewsIngestResult(
            inserted=inserted,
            scanned=scanned,
            skipped=skipped,
            message=message,
        )

    def list_feed(
        self,
        db: Session,
        interests: UserNewsInterests,
        related_only: bool = False,
        limit: int = 20,
    ) -> list[tuple[NewsItem, bool, str]]:
        candidates = (
            db.query(NewsItem)
            .order_by(NewsItem.published_at.desc())
            .limit(limit * 8)
            .all()
        )
        ranked = filter_and_rank(
            candidates,
            interests,
            related_only=related_only,
            limit=limit,
        )
        return [(row.item, row.related, row.category) for row in ranked]
