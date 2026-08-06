"""PRD 契约测试 — 固化 §二/§4.1/§五/§七 的关键契约，防止接线回归。

原则：每条契约 = 一个可读断言；不依赖网络/LLM；失败即 PRD 契约破裂。
"""

from __future__ import annotations

from stockresearch.agents.market.research_stream import run_market_research_stream
from stockresearch.services.user_preferences import _coerce_mode_settings


def test_research_mode_defaults_debate_on() -> None:
    """PRD §二：research 模式辩论默认开（未显式设置时）。"""
    settings = _coerce_mode_settings({"mode": "research"})
    assert settings.enable_debate is True
    assert settings.enable_glossary is False


def test_research_mode_explicit_debate_off_respected() -> None:
    """用户显式关闭辩论时，research 模式不得覆盖。"""
    settings = _coerce_mode_settings({"mode": "research", "enable_debate": False})
    assert settings.enable_debate is False


def test_advisor_mode_debate_stays_off() -> None:
    """PRD §二：个人模式辩论默认关。"""
    settings = _coerce_mode_settings({"mode": "advisor"})
    assert settings.enable_debate is False


def test_standard_reading_mode_normalized_to_friendly() -> None:
    """PRD §11.0：存量 standard 档归一为 friendly。"""
    settings = _coerce_mode_settings({"mode": "advisor", "reading_mode": "standard"})
    assert settings.reading_mode == "friendly"


def test_analysis_depth_defaults_by_mode() -> None:
    """PRD §4.1：advisor→standard，research→comprehensive。"""
    advisor = _coerce_mode_settings({"mode": "advisor"})
    research = _coerce_mode_settings({"mode": "research"})
    assert advisor.analysis_depth == "standard"
    assert research.analysis_depth == "comprehensive"


def test_market_research_stream_honors_depth_signature() -> None:
    """PRD §4.1：市场研究流必须接受并解析 analysis_depth（不恒为 standard）。"""
    import inspect

    sig = inspect.signature(run_market_research_stream)
    assert "analysis_depth" in sig.parameters
    from stockresearch.agents.market.research_stream import resolve_analysis_depth

    assert resolve_analysis_depth(explicit="deep", settings_depth="standard") == "deep"
