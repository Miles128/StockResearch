"""Tushare helper unit tests."""

from stockresearch.data.providers import tushare_financial as tf


def test_ts_code_sh_sz_bj() -> None:
    assert tf._ts_code("600519") == "600519.SH"
    assert tf._ts_code("000001") == "000001.SZ"
    assert tf._ts_code("430047") == "430047.BJ"
    assert tf._ts_code("920000") == "920000.BJ"


def test_probe_no_token() -> None:
    assert tf.probe_tushare_token("") == "no_token"
    assert tf.probe_tushare_token(None) == "no_token"
