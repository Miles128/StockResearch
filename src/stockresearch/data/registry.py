"""Data provider registry — tracks quote/overview fetch sources and degradation."""

import time
from dataclasses import dataclass
from datetime import UTC, datetime

_PRIMARY_QUOTES = "sina"
_FALLBACK_QUOTES = "akshare"
_TERTIARY_QUOTES = "efinance"

_SNAPSHOT_TTL_SECONDS = 300  # 5-minute TTL for provider snapshots


@dataclass(frozen=True)
class ProviderSnapshot:
    domain: str
    primary: str
    fallback: str | None
    primary_count: int
    fallback_count: int
    degraded: bool
    message: str | None
    updated_at: datetime
    tertiary: str | None = None
    tertiary_count: int = 0


_snapshots: dict[str, ProviderSnapshot] = {}
_symbol_sources: dict[str, str] = {}


def record_quote_fetch(
    *,
    requested: int,
    sina_count: int,
    akshare_count: int,
    efinance_count: int = 0,
    message: str | None = None,
) -> None:
    degraded = akshare_count > 0 or efinance_count > 0 or (sina_count < requested and requested > 0)
    if requested == 0:
        msg = message
    elif efinance_count > 0:
        msg = message or f"部分标的已降级至 {_FALLBACK_QUOTES}/{_TERTIARY_QUOTES}"
    elif akshare_count > 0:
        msg = message or f"部分标的已降级至 {_FALLBACK_QUOTES}"
    elif sina_count < requested:
        msg = message or "部分标的行情未获取"
    else:
        msg = message
    _snapshots["quotes"] = ProviderSnapshot(
        domain="quotes",
        primary=_PRIMARY_QUOTES,
        fallback=_FALLBACK_QUOTES if akshare_count else None,
        primary_count=sina_count,
        fallback_count=akshare_count,
        degraded=degraded,
        message=msg,
        updated_at=datetime.now(UTC),
        tertiary=_TERTIARY_QUOTES if efinance_count else None,
        tertiary_count=efinance_count,
    )


def record_symbol_sources(sources: dict[str, str]) -> None:
    global _symbol_sources
    _symbol_sources.update(sources)


def get_symbol_source(symbol: str) -> str | None:
    return _symbol_sources.get(symbol)


def record_overview_fetch(
    *,
    source: str,
    degraded: bool,
    message: str | None = None,
) -> None:
    primary = _PRIMARY_QUOTES if source == _PRIMARY_QUOTES else source
    fallback = _FALLBACK_QUOTES if source == _FALLBACK_QUOTES else None
    _snapshots["overview"] = ProviderSnapshot(
        domain="overview",
        primary=primary,
        fallback=fallback if degraded and source != _PRIMARY_QUOTES else None,
        primary_count=1 if source == _PRIMARY_QUOTES else 0,
        fallback_count=1 if source == _FALLBACK_QUOTES else 0,
        degraded=degraded,
        message=message,
        updated_at=datetime.now(UTC),
    )


def get_snapshots() -> dict[str, ProviderSnapshot]:
    _clear_expired_snapshots()
    return dict(_snapshots)


def _clear_expired_snapshots() -> None:
    now = datetime.now(UTC)
    expired = [
        k for k, v in _snapshots.items()
        if (now - v.updated_at).total_seconds() > _SNAPSHOT_TTL_SECONDS
    ]
    for k in expired:
        del _snapshots[k]


def reset_snapshots_for_tests() -> None:
    global _symbol_sources
    _snapshots.clear()
    _symbol_sources.clear()
