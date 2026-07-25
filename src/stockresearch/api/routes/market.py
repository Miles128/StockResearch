"""Market data routes."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.core.schemas import (
    DataSourceDetailOut,
    DataSourceStatusOut,
    IndexIntradayOut,
    IntradayPointOut,
    KlineChartOut,
    MarketOverviewOut,
    ProviderMetaOut,
    ProviderStatusOut,
    QuotePriceConflictOut,
    SectorBoardOut,
    SectorMoversOut,
    SentimentDriverOut,
    SentimentOut,
    StockQuoteOut,
)
from stockresearch.data.providers.sina_kline import fetch_sina_intraday
from stockresearch.services.sentiment import SentimentService
from stockresearch.data.provider_meta import list_provider_catalog
from stockresearch.data.providers.market import TechnicalDataProvider
from stockresearch.data.providers.market_overview import BatchQuoteProvider, MarketOverviewProvider
from stockresearch.data.providers.sector import SectorDataProvider
from stockresearch.data.registry import ProviderSnapshot, get_quote_conflicts, get_snapshots
from stockresearch.db.models import Holding, User
from stockresearch.db.session import get_db
from stockresearch.services.provider_cache_policy import quote_cache_ttl_seconds
from stockresearch.services.user_preferences import get_mode_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/overview", response_model=MarketOverviewOut)
async def market_overview(
    _user: User = Depends(get_current_user),
) -> MarketOverviewOut:
    return await MarketOverviewProvider().get_overview()


@router.get("/quotes", response_model=list[StockQuoteOut])
async def stock_quotes(
    symbols: str = Query(default="", description="Comma-separated symbols, e.g. 600519,300750"),
    force_refresh: bool = Query(default=False, description="Bypass quote cache for live refresh"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StockQuoteOut]:
    symbol_list = list(dict.fromkeys(s.strip() for s in symbols.split(",") if s.strip()))
    if not symbol_list:
        holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
        symbol_list = list(dict.fromkeys(h.symbol for h in holdings))
    if not symbol_list:
        return []
    mode = get_mode_settings(db, user.id)
    ttl = quote_cache_ttl_seconds(mode)
    return await BatchQuoteProvider().get_quotes(
        symbol_list,
        cache_ttl_seconds=ttl,
        force_refresh=force_refresh,
    )


def _sector_board_out(board) -> SectorBoardOut:
    return SectorBoardOut(
        code=board.code,
        name=board.name,
        change_pct=board.change_pct,
        leader_name=board.leader_name,
        leader_symbol=board.leader_symbol,
        leader_change_pct=board.leader_change_pct,
    )


@router.get("/sectors", response_model=SectorMoversOut)
async def sector_movers(
    limit: int = Query(default=8, ge=3, le=20),
    all_boards: bool = Query(default=False, alias="all"),
    _user: User = Depends(get_current_user),
) -> SectorMoversOut:
    boards = await SectorDataProvider().fetch_industry_boards()
    sorted_boards = sorted(boards, key=lambda b: b.change_pct, reverse=True)
    if all_boards:
        return SectorMoversOut(
            boards=[_sector_board_out(b) for b in sorted_boards],
            updated_at=datetime.now(UTC),
        )
    gainers = [_sector_board_out(b) for b in sorted_boards[:limit]]
    losers = [_sector_board_out(b) for b in sorted_boards[-limit:][::-1]]
    return SectorMoversOut(gainers=gainers, losers=losers, updated_at=datetime.now(UTC))


@router.get("/intraday", response_model=list[IndexIntradayOut])
async def index_intraday(
    symbols: str = Query(..., description="Comma-separated index symbols, e.g. 000001,399001"),
    _user: User = Depends(get_current_user),
) -> list[IndexIntradayOut]:
    symbol_list = list(dict.fromkeys(s.strip() for s in symbols.split(",") if s.strip()))
    results: list[IndexIntradayOut] = []
    for symbol in symbol_list:
        try:
            raw = await asyncio.to_thread(fetch_sina_intraday, symbol)
            points = [IntradayPointOut(time=str(p["time"]), price=float(p["price"])) for p in raw]
        except Exception:
            logger.warning("intraday fetch failed for %s", symbol, exc_info=True)
            points = []
        results.append(IndexIntradayOut(symbol=symbol, points=points))
    return results


@router.get("/kline", response_model=KlineChartOut)
async def stock_kline(
    symbol: str = Query(min_length=6, max_length=6, pattern=r"^\d{6}$"),
    days: int = Query(default=90, ge=10, le=500),
    before: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _user: User = Depends(get_current_user),
) -> KlineChartOut:
    raw = await TechnicalDataProvider().get_kline_chart(symbol, days, before=before)
    if not raw.get("bars"):
        raise HTTPException(
            status_code=503,
            detail="K 线数据暂不可用（行情源连接失败），请稍后刷新",
        )
    return KlineChartOut.model_validate(raw)


@router.get("/data-status", response_model=DataSourceStatusOut)
async def data_source_status(
    _user: User = Depends(get_current_user),
) -> DataSourceStatusOut:
    snapshots = get_snapshots()
    quotes = snapshots.get("quotes")
    overview = snapshots.get("overview")
    from stockresearch.data.providers.tushare_financial import probe_tushare_token

    tushare_status = await asyncio.to_thread(probe_tushare_token)
    tushare_configured = tushare_status != "no_token"
    tushare_available = tushare_status == "ok"
    quote_status = _provider_status(quotes) if quotes else None
    overview_status = _provider_status(overview) if overview else None
    return DataSourceStatusOut(
        quotes=quote_status,
        overview=overview_status,
        details=_data_source_details(
            quote_status,
            overview_status,
            tushare_configured=tushare_configured,
            tushare_available=tushare_available,
            tushare_status=tushare_status,
        ),
        provider_catalog=[
            ProviderMetaOut(
                key=meta.key,
                label=meta.label,
                layer=meta.layer,
                provider=meta.provider,
                domain=meta.domain,
                default_ttl_seconds=meta.default_ttl_seconds,
            )
            for meta in list_provider_catalog()
        ],
        use_mock=False,
        tushare_configured=tushare_configured,
        tushare_available=tushare_available,
        tushare_status=tushare_status,
        price_conflicts=[
            QuotePriceConflictOut(
                symbol=item.symbol,
                name=item.name,
                primary_source=item.primary_source,
                primary_price=item.primary_price,
                compare_source=item.compare_source,
                compare_price=item.compare_price,
                diff_pct=item.diff_pct,
            )
            for item in get_quote_conflicts()
        ],
    )


def _provider_status(snapshot: ProviderSnapshot) -> ProviderStatusOut:
    confidence: Literal["verified", "single_source", "delayed", "cached", "conflict", "missing"] = "single_source"
    if snapshot.degraded:
        confidence = "missing" if snapshot.fallback_count == 0 and snapshot.tertiary_count == 0 else "cached"
    return ProviderStatusOut(
        domain=snapshot.domain,
        primary=snapshot.primary,
        fallback=snapshot.fallback,
        tertiary=snapshot.tertiary,
        primary_count=snapshot.primary_count,
        fallback_count=snapshot.fallback_count,
        tertiary_count=snapshot.tertiary_count,
        degraded=snapshot.degraded,
        message=snapshot.message,
        updated_at=snapshot.updated_at,
        layer="L1",
        is_cached=False,
        is_mock=False,
        degraded_reason=snapshot.message if snapshot.degraded else None,
        confidence=confidence,
    )


def _data_source_details(
    quotes: ProviderStatusOut | None,
    overview: ProviderStatusOut | None,
    *,
    tushare_configured: bool,
    tushare_available: bool,
    tushare_status: str = "no_token",
) -> list[DataSourceDetailOut]:
    """返回所有已配置数据源的清单（不只是本次会话实际触发的）。

    静态条目：sina/akshare/eastmoney/tushare 总是列出，让前端能看到完整源清单。
    动态条目：本次会话实际触发过的 domain（quotes/overview）会带 fetched_at 与真实状态。
    """
    details: list[DataSourceDetailOut] = []

    # ── L1 实时行情：sina 主 + akshare 备 + efinance 兜底 ──
    if quotes is None:
        details.append(
            DataSourceDetailOut(
                domain="quotes",
                label="行情报价",
                layer="L1",
                source="sina + akshare + efinance",
                confidence="single_source",
                status="configured",
            )
        )
    else:
        sources = [quotes.primary]
        if quotes.fallback:
            sources.append(quotes.fallback)
        if quotes.tertiary:
            sources.append(quotes.tertiary)
        source = " + ".join(sources)
        details.append(
            DataSourceDetailOut(
                domain=quotes.domain,
                label="行情报价",
                layer=quotes.layer,
                source=source,
                fetched_at=quotes.updated_at,
                latency_ms=quotes.latency_ms,
                is_cached=quotes.is_cached,
                is_mock=quotes.is_mock,
                degraded=quotes.degraded,
                degraded_reason=quotes.degraded_reason or quotes.message,
                confidence=quotes.confidence,
                status="degraded" if quotes.degraded else "ok",
            )
        )

    # ── L1 市场概览：sina 主 + akshare 备 ──
    if overview is None:
        details.append(
            DataSourceDetailOut(
                domain="overview",
                label="市场概览",
                layer="L1",
                source="sina + akshare",
                confidence="single_source",
                status="configured",
            )
        )
    else:
        source = overview.primary if not overview.fallback else f"{overview.primary} + {overview.fallback}"
        details.append(
            DataSourceDetailOut(
                domain=overview.domain,
                label="市场概览",
                layer=overview.layer,
                source=source,
                fetched_at=overview.updated_at,
                latency_ms=overview.latency_ms,
                is_cached=overview.is_cached,
                is_mock=overview.is_mock,
                degraded=overview.degraded,
                degraded_reason=overview.degraded_reason or overview.message,
                confidence=overview.confidence,
                status="degraded" if overview.degraded else "ok",
            )
        )

    # ── L2 历史数据：akshare（K线/龙虎榜/资金流/股东/解禁/财务估值）──
    details.append(
        DataSourceDetailOut(
            domain="historical",
            label="历史K线 / 龙虎榜 / 资金流 / 股东 / 解禁 / 财务估值",
            layer="L2",
            source="akshare",
            confidence="single_source",
            status="ok",
        )
    )

    # ── L2 板块行业：eastmoney ──
    details.append(
        DataSourceDetailOut(
            domain="sector",
            label="板块行业 / 个股归属",
            layer="L2",
            source="eastmoney",
            confidence="single_source",
            status="ok",
        )
    )

    # ── L2 新闻文本：eastmoney 主 + akshare 备 + bocha 兜底 ──
    details.append(
        DataSourceDetailOut(
            domain="news",
            label="新闻 / 快讯",
            layer="L2",
            source="eastmoney + akshare(cls/ths/sina) + bocha",
            confidence="single_source",
            status="ok",
        )
    )

    # ── L2 情绪：雪球 + eastmoney ──
    details.append(
        DataSourceDetailOut(
            domain="sentiment",
            label="情绪热度 / 评分",
            layer="L2",
            source="xueqiu + eastmoney + news",
            confidence="single_source",
            status="ok",
        )
    )

    # ── L3 Tushare Pro：估值兜底 / 日线 qfq 兜底 ──
    tushare_reason = {
        "no_token": None,
        "unavailable": "Python 运行环境未安装 tushare",
        "invalid": "Token 无效或鉴权失败",
        "quota": "积分不足或接口权限不够，已跳过 Tushare 兜底",
        "ok": None,
    }.get(tushare_status)
    tushare_detail_status = {
        "ok": "ok",
        "no_token": "not_configured",
        "unavailable": "degraded",
        "invalid": "degraded",
        "quota": "degraded",
    }.get(tushare_status, "not_configured")
    details.append(
        DataSourceDetailOut(
            domain="tushare",
            label="Tushare Pro（估值 / 日线 qfq 兜底）",
            layer="L3",
            source="tushare",
            degraded=tushare_configured and not tushare_available,
            degraded_reason=tushare_reason,
            confidence="single_source" if tushare_available else "missing",
            status=tushare_detail_status,
        )
    )
    return details


@router.get("/sentiment", response_model=SentimentOut)
async def market_sentiment(
    _user: User = Depends(get_current_user),
) -> SentimentOut:
    result = await SentimentService().compute_market_sentiment()
    return SentimentOut(
        score=result.score,
        label=result.label,
        drivers=[SentimentDriverOut(label=d.label, value=d.value, impact=d.impact) for d in result.drivers],
        source=result.source,
    )


@router.get("/sector-sentiment", response_model=SentimentOut)
async def sector_sentiment(
    name: str = Query(..., min_length=1),
    _user: User = Depends(get_current_user),
) -> SentimentOut:
    result = await SentimentService().compute_sector_sentiment(name)
    return SentimentOut(
        score=result.score,
        label=result.label,
        drivers=[SentimentDriverOut(label=d.label, value=d.value, impact=d.impact) for d in result.drivers],
        source=result.source,
    )


@router.get("/stock-sentiment", response_model=SentimentOut)
async def stock_sentiment(
    symbol: str = Query(..., min_length=6, max_length=6, pattern=r"^\d{6}$"),
    name: str = Query(default=""),
    _user: User = Depends(get_current_user),
) -> SentimentOut:
    result = await SentimentService().compute_stock_sentiment(symbol, name)
    return SentimentOut(
        score=result.score,
        label=result.label,
        drivers=[SentimentDriverOut(label=d.label, value=d.value, impact=d.impact) for d in result.drivers],
        source=result.source,
    )
