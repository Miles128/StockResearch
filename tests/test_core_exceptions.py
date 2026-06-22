"""Tests for custom exception hierarchy."""

from stockresearch.core.exceptions import (
    AgentError,
    DataProviderError,
    NotFoundError,
    StockResearchError,
    ValidationError,
)


def test_stock_research_error_is_base() -> None:
    e = StockResearchError("base error")
    assert isinstance(e, Exception)
    assert str(e) == "base error"


def test_not_found_error_inherits_base() -> None:
    e = NotFoundError("not found")
    assert isinstance(e, StockResearchError)


def test_validation_error_inherits_base() -> None:
    e = ValidationError("bad input")
    assert isinstance(e, StockResearchError)


def test_data_provider_error_inherits_base() -> None:
    e = DataProviderError("api down")
    assert isinstance(e, StockResearchError)


def test_agent_error_inherits_base() -> None:
    e = AgentError("agent failed")
    assert isinstance(e, StockResearchError)


def test_subtypes_are_distinct() -> None:
    errors = [NotFoundError, ValidationError, DataProviderError, AgentError]
    instances = [cls("msg") for cls in errors]
    types = {type(e) for e in instances}
    assert len(types) == len(errors)
