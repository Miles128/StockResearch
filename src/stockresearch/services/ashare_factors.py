"""A-share evidence-coverage checklist (not numeric investable factors).

Numeric factors live in ``stockresearch.services.factors``. This module only
marks which research data sources were present in the current report.
"""

from typing import Literal

from stockresearch.core.schemas import AshareFactorOut, DimensionResult, FactorSourceOut

_SOURCE_META: dict[str, tuple[str, str, str]] = {
    "sina_trading_rules": ("涨跌停 / ST / 停复牌状态", "L1", "sina"),
    "sina_quote": ("实时行情", "L1", "sina"),
    "akshare_kline": ("K 线与技术指标", "L2", "akshare"),
    "akshare_lhb": ("龙虎榜", "L2", "akshare"),
    "akshare_fund_flow": ("主力资金流向", "L2", "akshare"),
    "akshare_northbound": ("北向资金", "L2", "akshare"),
    "akshare_margin": ("融资融券", "L2", "akshare"),
    "akshare_gdhs": ("股东户数", "L2", "akshare"),
    "akshare_lockup": ("限售解禁", "L2", "akshare"),
    "akshare_financials": ("财务与估值", "L2", "akshare"),
    "akshare_valuation": ("估值分位", "L2", "akshare"),
    "akshare_peers": ("可比公司", "L2", "akshare"),
    "ths_ratio_snapshot": ("同花顺比率摘要", "L2", "ths"),
    "cninfo_announcements": ("巨潮公告", "L1", "cninfo"),
    "em_research_reports": ("机构研报", "L2", "eastmoney"),
    "xueqiu_hot": ("雪球/东财情绪热度", "L2", "xueqiu"),
    "news_text_factor": ("新闻文本因子", "L1", "news"),
}


def build_ashare_factor_checklist(
    dimensions: dict[str, DimensionResult],
    *,
    news_text_factor: str | None = None,
) -> list[AshareFactorOut]:
    """Build a lightweight A-share factor checklist from existing evidence.

    The checklist intentionally does not invent new market facts. It only marks a
    factor as verified when the current report already contains a matching data
    source or explicit text evidence; otherwise it records what is missing.
    """
    sources = {
        source
        for dim in dimensions.values()
        for source in dim.data_sources
    }

    return [
        _source_factor(
            category="制度与交易规则",
            name="涨跌停 / ST / 停复牌",
            impact="liquidity",
            sources=sources,
            required={"sina_trading_rules"},
            evidence_label="涨跌停 / ST / 停复牌状态",
            missing_label="涨跌停、ST、停复牌状态源",
        ),
        _source_factor(
            category="资金与筹码",
            name="龙虎榜与游资席位",
            impact="sentiment",
            sources=sources,
            required={"akshare_lhb"},
            evidence_label="龙虎榜数据",
            missing_label="龙虎榜 / 游资席位",
        ),
        _source_factor(
            category="资金与筹码",
            name="主力资金流向",
            impact="sentiment",
            sources=sources,
            required={"akshare_fund_flow"},
            evidence_label="主力资金流向",
            missing_label="主力资金流向",
        ),
        _source_factor(
            category="资金与筹码",
            name="北向资金",
            impact="sentiment",
            sources=sources,
            required={"akshare_northbound"},
            evidence_label="北向资金",
            missing_label="北向资金",
        ),
        _source_factor(
            category="资金与筹码",
            name="融资融券",
            impact="sentiment",
            sources=sources,
            required={"akshare_margin"},
            evidence_label="融资融券",
            missing_label="融资融券",
        ),
        _source_factor(
            category="资金与筹码",
            name="雪球/东财情绪",
            impact="sentiment",
            sources=sources,
            required={"xueqiu_hot"},
            evidence_label="雪球/东财情绪热度",
            missing_label="雪球热度或多空比",
        ),
        _source_factor(
            category="供给冲击与股权事件",
            name="限售解禁",
            impact="event",
            sources=sources,
            required={"akshare_lockup"},
            evidence_label="限售解禁数据",
            missing_label="限售解禁数据",
        ),
        _source_factor(
            category="财务与质量",
            name="财务质量与估值",
            impact="fundamental",
            sources=sources,
            required={"akshare_financials"},
            evidence_label="财务与估值数据",
            missing_label="财务与估值数据",
        ),
        _source_factor(
            category="技术与市场结构",
            name="K 线、均线与技术指标",
            impact="technical",
            sources=sources,
            required={"akshare_kline", "sina_quote"},
            evidence_label="K 线与实时行情",
            missing_label="K 线 / 实时行情",
        ),
        AshareFactorOut(
            category="政策、行业与主题",
            name="新闻、政策与事件文本",
            status="verified" if news_text_factor else "missing",
            impact="event",
            evidence=["新闻文本因子已生成"] if news_text_factor else [],
            missing=[] if news_text_factor else ["尚未获取或生成新闻文本因子"],
            source_details=_source_details(
                matched={"news_text_factor"} if news_text_factor else set(),
                missing=set() if news_text_factor else {"news_text_factor"},
            ),
        ),
    ]


def _source_factor(
    *,
    category: str,
    name: str,
    impact: Literal["liquidity", "sentiment", "fundamental", "valuation", "event", "technical"],
    sources: set[str],
    required: set[str],
    evidence_label: str,
    missing_label: str,
) -> AshareFactorOut:
    matched = sorted(required & sources)
    missing = sorted(required - sources)
    status: Literal["verified", "partial", "missing"] = (
        "verified" if not missing else "partial" if matched else "missing"
    )
    return AshareFactorOut(
        category=category,
        name=name,
        status=status,
        impact=impact,
        evidence=[f"{evidence_label}：{', '.join(matched)}"] if matched else [],
        missing=[f"缺少{missing_label}：{', '.join(missing)}"] if missing else [],
        source_details=_source_details(matched=set(matched), missing=set(missing)),
    )


def _source_details(*, matched: set[str], missing: set[str]) -> list[FactorSourceOut]:
    details: list[FactorSourceOut] = []
    for key in sorted(matched):
        label, layer, provider = _source_meta(key)
        details.append(
            FactorSourceOut(
                key=key,
                label=label,
                layer=layer,
                provider=provider,
                status="verified",
            )
        )
    for key in sorted(missing):
        label, layer, provider = _source_meta(key)
        details.append(
            FactorSourceOut(
                key=key,
                label=label,
                layer=layer,
                provider=provider,
                status="missing",
                note="本次研究未获取该来源",
            )
        )
    return details


def _source_meta(key: str) -> tuple[str, str, str]:
    return _SOURCE_META.get(key, (key, "L1", key.split("_", maxsplit=1)[0]))
