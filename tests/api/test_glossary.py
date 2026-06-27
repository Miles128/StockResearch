"""Glossary API endpoint tests."""


def test_glossary_returns_terms(client) -> None:
    resp = client.get("/api/v1/glossary")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 30  # glossary.json 至少 30 条


def test_glossary_term_has_required_fields(client) -> None:
    resp = client.get("/api/v1/glossary")
    data = resp.json()
    by_id = {t["id"]: t for t in data}
    pe = by_id["PE"]
    assert pe["short"] == "市盈率"
    assert pe["en"] == "Price-to-Earnings Ratio"
    assert pe["def"]
    assert pe["analogy"]
