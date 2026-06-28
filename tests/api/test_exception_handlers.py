"""Exception handler status code tests."""

import pytest
from starlette.requests import Request

from stockresearch.api.app import create_app
from stockresearch.core.exceptions import AgentError, DataProviderError, LLMConfigError, StockResearchError


@pytest.fixture()
def exception_handler():
    app = create_app()
    return app.exception_handlers[StockResearchError]


@pytest.mark.asyncio
async def test_llm_config_error_returns_503(exception_handler) -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    response = await exception_handler(request, LLMConfigError("missing key"))
    assert response.status_code == 503
    body = response.body.decode()
    assert "llm_not_configured" in body


@pytest.mark.asyncio
async def test_data_provider_error_returns_502(exception_handler) -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    response = await exception_handler(request, DataProviderError("provider down"))
    assert response.status_code == 502
    assert "data_provider_failed" in response.body.decode()


@pytest.mark.asyncio
async def test_agent_error_returns_500(exception_handler) -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    response = await exception_handler(request, AgentError("agent failed"))
    assert response.status_code == 500
    assert "agent_failed" in response.body.decode()
