from stockresearch.core.schemas import ChatUserContext, ModeSettingsOut
from stockresearch.services.chat_context import build_long_term_context, format_user_context_block


def test_build_long_term_context_includes_holdings() -> None:
    class _H:
        symbol = "600519"
        name = "贵州茅台"
        sector = "白酒"

    text = build_long_term_context(mode_settings=ModeSettingsOut(), holdings=[_H()])  # type: ignore[list-item]
    assert "贵州茅台" in text
    assert "个人投顾" in text or "advisor" not in text


def test_format_user_context_block() -> None:
    ctx = ChatUserContext(kind="stock", label="贵州茅台 600519", detail="白酒", symbol="600519")
    block = format_user_context_block(ctx)
    assert "贵州茅台 600519" in block
    assert "600519" in block
