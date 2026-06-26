"""Market data routes."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.core.config import get_settings
from stockresearch.core.data_source_config import get_tushare_token
from stockresearch.core.schemas import (
    DataSourceDetailOut,
    DataSourceStatusOut,
    KlineChartOut,
    MarketOverviewOut,
    ProviderStatusOut,
    StockQuoteOut,
)
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
    use_mock = get_settings().use_mock_market_data
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
            use_mock=use_mock,
            tushare_configured=tushare_configured,
            tushare_available=tushare_available,
        ),
        use_mock=use_mock,
        tushare_configured=tushare_configured,
        tushare_available=tushare_available,
    )


def _provider_status(snapshot: ProviderSnapshot) -> ProviderStatusOut:
    confidence: Literal["verified", "single_source", "delayed", "cached", "conflict", "missing"] = "single_source"
    if snapshot.degraded:
        confidence = "missing" if snapshot.fallback_count == 0 else "cached"
    return ProviderStatusOut(
        domain=snapshot.domain,
        primary=snapshot.primary,
        fallback=snapshot.fallback,
        primary_count=snapshot.primary_count,
        fallback_count=snapshot.fallback_count,
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
    use_mock: bool,
    tushare_configured: bool,
    tushare_available: bool,
) -> list[DataSourceDetailOut]:
    details: list[DataSourceDetailOut] = []
    for item, label in ((overview, "市场概览"), (quotes, "行情报价")):
        if item is None:
            details.append(
                DataSourceDetailOut(
                    domain=label,
                    label=label,
                    layer="L1",
                    source="未获取",
                    degraded=True,
                    degraded_reason="本次会话尚未获取该类数据",
                    confidence="missing",
                    status="missing",
                )
            )
            continue
        source = item.primary if not item.fallback else f"{item.primary} → {item.fallback}"
        details.append(
            DataSourceDetailOut(
                domain=item.domain,
                label=label,
                layer=item.layer,
                source=source,
                fetched_at=item.updated_at,
                latency_ms=item.latency_ms,
                is_cached=item.is_cached,
                is_mock=item.is_mock,
                degraded=item.degraded,
                degraded_reason=item.degraded_reason or item.message,
                confidence=item.confidence,
                status="degraded" if item.degraded else "ok",
            )
        )
    details.append(
        DataSourceDetailOut(
            domain="mock",
            label="Mock 演示数据",
            layer="L0",
            source="local",
            is_mock=use_mock,
            confidence="single_source",
            status="mock" if use_mock else "not_configured",
        )
    )
    details.append(
        DataSourceDetailOut(
            domain="tushare",
            label="Tushare Pro 增强数据",
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
