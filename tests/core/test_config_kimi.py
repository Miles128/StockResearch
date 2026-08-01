from stockresearch.core.config import Settings


def test_kimi_settings_defaults() -> None:
    s = Settings()
    assert s.kimi_cli_enabled is False
    assert s.kimi_cli_path == "kimi"
    assert s.kimi_cli_timeout_seconds == 120
    assert s.kimi_live_max_calls_per_day == 20


def test_kimi_settings_from_env(monkeypatch) -> None:
    monkeypatch.setenv("KIMI_CLI_ENABLED", "true")
    monkeypatch.setenv("KIMI_CLI_TIMEOUT_SECONDS", "60")
    s = Settings()
    assert s.kimi_cli_enabled is True
    assert s.kimi_cli_timeout_seconds == 60
