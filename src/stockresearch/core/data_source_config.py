"""Per-request data-source overrides (e.g. Tushare/Bocha tokens from client settings)."""

from contextvars import ContextVar

_tushare_token: ContextVar[str | None] = ContextVar("tushare_token", default=None)
_bocha_api_key: ContextVar[str | None] = ContextVar("bocha_api_key", default=None)


def set_tushare_token(token: str | None) -> None:
    cleaned = token.strip() if token else None
    _tushare_token.set(cleaned or None)


def get_tushare_token() -> str | None:
    return _tushare_token.get()


def set_bocha_api_key(key: str | None) -> None:
    cleaned = key.strip() if key else None
    _bocha_api_key.set(cleaned or None)


def get_bocha_api_key() -> str | None:
    return _bocha_api_key.get()


def clear_data_source_context() -> None:
    _tushare_token.set(None)
    _bocha_api_key.set(None)
