"""Tests for core configuration."""

from stockresearch.core.config import Settings, get_settings


def test_settings_defaults() -> None:
    s = Settings()
    assert s.use_mock_llm is True
    assert s.database_url.startswith("sqlite")
    assert s.research_cache_ttl_seconds == 86400
    assert s.agent_timeout_seconds == 45


def test_settings_with_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-test-key")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("USE_MOCK_LLM", "false")
    get_settings.cache_clear()
    s = get_settings()
    assert s.llm_api_key == "sk-test-key"
    assert s.llm_model == "gpt-4o"
    assert s.use_mock_llm is False
    get_settings.cache_clear()


def test_get_settings_returns_settings_instance() -> None:
    get_settings.cache_clear()
    s = get_settings()
    assert isinstance(s, Settings)
    get_settings.cache_clear()


def test_cors_allowed_origins_default_empty() -> None:
    s = Settings()
    assert s.cors_allowed_origins == ""
