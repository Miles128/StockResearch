from datetime import UTC, datetime

import pytest

from stockresearch.core.schemas import ChatUserContext, ModeSettingsOut
from stockresearch.data.providers.market import Quote, QuoteProvider
from stockresearch.services.chat.context import build_long_term_context, format_user_context_block


@pytest.mark.asyncio
async def test_build_long_term_context_includes_holdings(monkeypatch: pytest.MonkeyPatch) -> None:
    class _H:
        symbol = "600519"
        name = "贵州茅台"
        sector = "白酒"

    async def _fake_quotes(
        _self: QuoteProvider,
        _symbols: list[str],
        *,
        cache_ttl_seconds: int | None = None,
    ) -> dict[str, Quote]:
        return {
            "600519": Quote(
                symbol="600519",
                name="贵州茅台",
                price=1680.0,
                change_pct=1.2,
                open=1670.0,
                high=1690.0,
                low=1670.0,
                volume=1000.0,
                updated_at=datetime.now(UTC),
            )
        }

    monkeypatch.setattr(QuoteProvider, "get_quotes", _fake_quotes)
    text = await build_long_term_context(
        mode_settings=ModeSettingsOut(mode="research"),
        holdings=[_H()],  # type: ignore[list-item]
        message="我的持仓怎么样",
    )
    assert "贵州茅台" in text
    assert "1680.00" in text
    assert "持仓行情" in text
    assert "个人版表达要求" not in text


@pytest.mark.asyncio
async def test_build_long_term_context_advisor_plain_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_quotes(
        _self: QuoteProvider,
        _symbols: list[str],
        *,
        cache_ttl_seconds: int | None = None,
    ) -> dict[str, Quote]:
        return {}

    monkeypatch.setattr(QuoteProvider, "get_quotes", _fake_quotes)
    text = await build_long_term_context(mode_settings=ModeSettingsOut(mode="advisor"), holdings=[])
    assert "个人版表达要求" in text


@pytest.mark.asyncio
async def test_build_long_term_context_defers_holdings_for_stock_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _H:
        symbol = "600519"
        name = "贵州茅台"
        sector = "白酒"

    async def _fake_quotes(
        _self: QuoteProvider,
        _symbols: list[str],
        *,
        cache_ttl_seconds: int | None = None,
    ) -> dict[str, Quote]:
        return {}

    monkeypatch.setattr(QuoteProvider, "get_quotes", _fake_quotes)
    text = await build_long_term_context(
        mode_settings=ModeSettingsOut(mode="advisor"),
        holdings=[_H()],  # type: ignore[name-defined]
        message="分析一下600519",
    )
    assert "勿主动结合或展开持仓分析" in text
    assert "1680" not in text


def test_format_user_context_block() -> None:
    ctx = ChatUserContext(kind="stock", label="贵州茅台 600519", detail="白酒", symbol="600519")
    block = format_user_context_block(ctx)
    assert "贵州茅台 600519" in block
    assert "600519" in block
