"""Market data routes."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.core.data_source_config import get_tushare_token
from stockresearch.core.schemas import (
    DataSourceDetailOut,
    DataSourceStatusOut,
    KlineChartOut,
    MarketOverviewOut,
    ProviderMetaOut,
    ProviderStatusOut,
    StockQuoteOut,
)
from stockresearch.data.provider_meta import list_provider_catalog
from stockresearch.data.providers.market import TechnicalDataProvider
from stockresearch.data.providers.market_overview import BatchQuoteProvider, MarketOverviewProvider
from stockresearch.data.registry import ProviderSnapshot, get_snapshots
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
    tushare_configured = bool(get_tushare_token())
    tushare_available = _tushare_runtime_available()
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
            source="eastmoney + akshare + bocha",
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
            source="xueqiu + eastmoney",
            confidence="single_source",
            status="ok",
        )
    )

    # ── L3 Tushare Pro 增强：估值/换手率 ──
    details.append(
        DataSourceDetailOut(
            domain="tushare",
            label="Tushare Pro 增强数据（PE/PB/换手率）",
            layer="L3",
            source="tushare",
            degraded=tushare_configured and not tushare_available,
            degraded_reason="Python 运行环境未安装 tushare" if tushare_configured and not tushare_available else None,
            confidence="single_source" if tushare_configured else "missing",
            status="configured" if tushare_configured and tushare_available else "not_configured",
        )
    )
    return details


def _tushare_runtime_available() -> bool:
    try:
        import tushare  # type: ignore[import-untyped]  # noqa: F401
    except ImportError:
        return False
    return True
