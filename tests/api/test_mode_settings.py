"""Mode/risk questionnaire persistence API."""


def test_get_mode_settings_defaults(client) -> None:
    resp = client.get("/api/v1/settings/mode")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "advisor"
    assert data["risk_tolerance"] == "moderate"
    assert data["reading_mode"] == "friendly"
    assert data["analysis_depth"] == "standard"
    assert data["onboarded"] is False


def test_put_mode_settings_persists(client) -> None:
    payload = {
        "mode": "advisor",
        "risk_tolerance": "conservative",
        "monthly_income": 18000,
        "reading_mode": "friendly",
        "analysis_depth": "comprehensive",
        "enable_debate": False,
        "enable_glossary": True,
        "custom_glossary": [],
        "quote_refresh_minutes": 10,
        "briefing_auto_enabled": True,
        "ui_polling_enabled": False,
        "max_signals": 5,
        "onboarded": True,
    }
    put_resp = client.put("/api/v1/settings/mode", json=payload)
    assert put_resp.status_code == 200
    assert put_resp.json() == payload

    get_resp = client.get("/api/v1/settings/mode")
    assert get_resp.status_code == 200
    assert get_resp.json() == payload
