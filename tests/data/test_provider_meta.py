"""Provider metadata catalog tests."""

from stockresearch.data.provider_meta import PROVIDER_CATALOG, get_provider_meta, list_provider_catalog


def test_provider_catalog_has_core_entries() -> None:
    assert "akshare_northbound" in PROVIDER_CATALOG
    assert "akshare_margin" in PROVIDER_CATALOG
    assert len(list_provider_catalog()) >= 10


def test_get_provider_meta_returns_ttl() -> None:
    meta = get_provider_meta("akshare_kline")
    assert meta is not None
    assert meta.layer == "L2"
    assert meta.default_ttl_seconds == 3600
