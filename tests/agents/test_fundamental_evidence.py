"""Tests for deepened fundamental tools and evidence schema."""

from stockresearch.agents.research.agents.fundamental import FUNDAMENTAL_AGENT, _build
from stockresearch.core.schemas import DimensionEvidence, DimensionResult, NumericFactorOut


def test_fundamental_tools_include_filings_and_reports() -> None:
    names = {t.name for t in FUNDAMENTAL_AGENT.tools}
    assert "cninfo_announcements" in names
    assert "em_research_reports" in names
    assert "ths_ratio_snapshot" in names


def test_fundamental_build_attaches_evidence_and_gaps() -> None:
    data = {
        "akshare_financials": {
            "revenue_yoy": 0.2,
            "roe": 0.18,
            "debt_ratio": 0.4,
            "partial": False,
        },
        "akshare_valuation": {
            "pe_percentile": None,
            "partial": True,
            "gaps": ["估值历史分位不可算"],
        },
        "akshare_peers": {"peers": [], "partial": True},
        "ths_ratio_snapshot": {"ratios": [], "partial": True},
        "cninfo_announcements": {
            "count": 1,
            "partial": False,
            "items": [
                {
                    "title": "2024年年度报告",
                    "announcement_type": "年报",
                    "announcement_time": "2025-03-01T00:00:00+00:00",
                    "url": "https://example.com/a",
                    "source": "cninfo",
                }
            ],
        },
        "em_research_reports": {
            "count": 1,
            "partial": False,
            "items": [
                {
                    "title": "深度报告",
                    "institution": "某券商",
                    "rating": "增持",
                    "publish_date": "2025-02-01T00:00:00+00:00",
                    "summary": "摘要",
                }
            ],
        },
    }
    result = _build(data, "亮点是增长。风险是竞争。")
    assert isinstance(result, DimensionResult)
    assert result.partial is True
    assert any(e.kind == "announcement" for e in result.evidence)
    assert any(e.kind == "research_report" for e in result.evidence)
    assert "估值历史分位缺失" in result.gaps
    assert "cninfo_announcements" in result.data_sources


def test_dimension_evidence_schema() -> None:
    ev = DimensionEvidence(source="cninfo", snippet="年报", date="2025-03-01", kind="announcement")
    assert ev.snippet == "年报"


def test_fundamental_build_treats_missing_roe_as_gap() -> None:
    data = {
        "akshare_financials": {
            "revenue_yoy": None,
            "roe": None,
            "debt_ratio": None,
            "partial": True,
            "gaps": ["财务指标序列不可用（THS/指标均失败）"],
        },
        "akshare_valuation": {"pe_percentile": None, "partial": True},
        "akshare_peers": {
            "peers": [{"symbol": "000858", "source": "seed"}],
            "partial": True,
            "gaps": ["可比公司仅种子兜底，非行业成份动态匹配"],
        },
        "ths_ratio_snapshot": {"ratios": [], "partial": True},
        "cninfo_announcements": {"count": 0, "partial": True, "items": []},
        "em_research_reports": {"count": 0, "partial": True, "items": []},
    }
    result = _build(data, "")
    assert result.partial is True
    assert any("缺失" in g or "不可用" in g for g in result.gaps)
    assert any("种子" in g for g in result.gaps)
    # Must not claim "ROE 0%" as a highlight from fabricated zero
    assert not any(h.startswith("ROE 0%") for h in result.highlights)


def test_numeric_factor_schema() -> None:
    factor = NumericFactorOut(
        key="momentum_20d", label="20日动量", value=3.2, unit="%", partial=False
    )
    assert factor.key == "momentum_20d"
