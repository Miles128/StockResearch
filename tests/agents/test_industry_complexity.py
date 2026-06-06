"""Industry research routing tests."""

from stockresearch.agents.orchestrator.complexity import (
    ComplexityResult,
    extract_industry_sector,
    is_industry_research,
    resolve_execution_mode,
)


def test_is_industry_research_without_stock() -> None:
    assert is_industry_research("半导体行业深度研究前景")
    assert not is_industry_research("帮我分析600519贵州茅台")


def test_extract_industry_sector() -> None:
    assert extract_industry_sector("新能源板块趋势怎么样") == "新能源"
    assert extract_industry_sector("持仓里的白酒怎么样", ["白酒", "银行"]) == "白酒"


def test_resolve_industry_mode() -> None:
    mode = resolve_execution_mode("医药行业深度投研分析")
    assert mode == ComplexityResult.INDUSTRY_RESEARCH
