"""Per-request data-source overrides (e.g. Tushare token from client settings)."""

from contextvars import ContextVar

_tushare_token: ContextVar[str | None] = ContextVar("tushare_token", default=None)


def set_tushare_token(token: str | None) -> None:
    cleaned = token.strip() if token else None
    _tushare_token.set(cleaned or None)


def get_tushare_token() -> str | None:
    return _tushare_token.get()


def clear_data_source_context() -> None:
    _tushare_token.set(None)
