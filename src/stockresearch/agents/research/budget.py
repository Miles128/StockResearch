"""Analysis depth budgets for four-dimension stock research."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

AnalysisDepth = Literal["standard", "comprehensive", "deep"]

BASE_FACTOR_KEYS: tuple[str, ...] = (
    "momentum_20d",
    "volatility_20d",
    "pe_percentile",
    "main_net_inflow_5d",
    "northbound_hold_pct",
)

QUALITY_FACTOR_KEYS: tuple[str, ...] = (
    "roe_ttm",
    "revenue_yoy",
    "np_yoy",
    "pb_percentile",
    "peer_rel_momentum_20d",
    "peer_rel_pe_percentile",
)

_DEPTH_ALIASES: dict[str, AnalysisDepth] = {
    "standard": "standard",
    "标准": "standard",
    "comprehensive": "comprehensive",
    "综合": "comprehensive",
    "deep": "deep",
    "深度": "deep",
}

# Prefer deep over comprehensive when both cues appear.
_DEEP_RE = re.compile(
    r"(深度分析|深入分析|深度挖|详细分析|全面深入|deep\s*analysis)",
    re.IGNORECASE,
)
_COMPREHENSIVE_RE = re.compile(
    r"(综合分析|综合研究|综合看看|全面分析|comprehensive)",
    re.IGNORECASE,
)
_GAP_CLOSE_RE = re.compile(
    r"(只补缺口|补缺口再跑|补充数据并重新投研|补充数据[：:])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AnalysisBudget:
    depth: AnalysisDepth
    ann_days: int
    ann_limit: int
    ann_excerpt_chars: int
    prefer_earnings_anns: bool
    include_risk_anns: bool
    report_limit: int
    financial_periods: int
    news_cluster: bool
    news_deep_cross_check: int
    factor_keys: tuple[str, ...]
    factors_expanded: bool
    enable_signal_verify_hook: bool


def normalize_analysis_depth(raw: object | None) -> AnalysisDepth | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    if text in _DEPTH_ALIASES:
        return _DEPTH_ALIASES[text]
    return None


def parse_depth_from_text(text: str | None) -> AnalysisDepth | None:
    if not text or not str(text).strip():
        return None
    blob = str(text)
    if _DEEP_RE.search(blob):
        return "deep"
    if _COMPREHENSIVE_RE.search(blob):
        return "comprehensive"
    return None


def is_gap_close_utterance(text: str | None) -> bool:
    """True when user asks to refill evidence gaps and re-run research."""
    if not text or not str(text).strip():
        return False
    return _GAP_CLOSE_RE.search(str(text)) is not None


def resolve_analysis_depth(
    *,
    explicit: object | None = None,
    utterance: str | None = None,
    settings_depth: object | None = None,
    default: AnalysisDepth = "standard",
) -> AnalysisDepth:
    """Priority: explicit arg > utterance cue > settings > default."""
    for candidate in (
        normalize_analysis_depth(explicit),
        parse_depth_from_text(utterance),
        normalize_analysis_depth(settings_depth),
    ):
        if candidate is not None:
            return candidate
    return default


def budget_for_depth(depth: AnalysisDepth) -> AnalysisBudget:
    if depth == "deep":
        return AnalysisBudget(
            depth="deep",
            ann_days=90,
            ann_limit=12,
            ann_excerpt_chars=400,
            prefer_earnings_anns=True,
            include_risk_anns=True,
            report_limit=8,
            financial_periods=10,
            news_cluster=True,
            news_deep_cross_check=2,
            factor_keys=BASE_FACTOR_KEYS + QUALITY_FACTOR_KEYS,
            factors_expanded=True,
            enable_signal_verify_hook=True,
        )
    if depth == "comprehensive":
        return AnalysisBudget(
            depth="comprehensive",
            ann_days=60,
            ann_limit=8,
            ann_excerpt_chars=320,
            prefer_earnings_anns=True,
            include_risk_anns=False,
            report_limit=6,
            financial_periods=6,
            news_cluster=True,
            news_deep_cross_check=0,
            factor_keys=BASE_FACTOR_KEYS + QUALITY_FACTOR_KEYS,
            factors_expanded=True,
            enable_signal_verify_hook=False,
        )
    return AnalysisBudget(
        depth="standard",
        ann_days=60,
        ann_limit=8,
        ann_excerpt_chars=200,
        prefer_earnings_anns=False,
        include_risk_anns=False,
        report_limit=6,
        financial_periods=2,
        news_cluster=False,
        news_deep_cross_check=0,
        factor_keys=BASE_FACTOR_KEYS,
        factors_expanded=False,
        enable_signal_verify_hook=False,
    )


def default_depth_for_mode(mode: str | None) -> AnalysisDepth:
    return "comprehensive" if mode == "research" else "standard"
