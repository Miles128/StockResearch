"""Symbol resolver tests."""

import pytest

from stockresearch.core.exceptions import ValidationError
from stockresearch.services.symbol_resolver import resolve_stock_query


def test_resolve_by_code() -> None:
    symbol, name = resolve_stock_query("600519")
    assert symbol == "600519"
    assert "茅台" in name


def test_resolve_by_name() -> None:
    symbol, name = resolve_stock_query("贵州茅台")
    assert symbol == "600519"
    assert name == "贵州茅台"


def test_resolve_empty_raises() -> None:
    with pytest.raises(ValidationError):
        resolve_stock_query("")
