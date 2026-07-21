"""Tests for fundamental evidence including valuation/financials."""

from stockresearch.agents.research.agents.fundamental import _collect_evidence


def test_collect_evidence_includes_financials_and_valuation() -> None:
    data = {
        "cninfo_announcements": {"items": []},
        "em_research_reports": {"items": []},
        "akshare_financials": {
            "partial": False,
            "revenue_yoy": 0.2,
            "roe": 0.18,
            "as_of": "2024-12-31",
        },
        "akshare_valuation": {"partial": False, "pe_percentile": 0.35, "as_of": "2025-01-01"},
    }
    evidence = _collect_evidence(data)
    kinds = {e.kind for e in evidence}
    assert "financial" in kinds
    assert any("PE" in e.snippet for e in evidence)
    assert any("财务" in e.snippet for e in evidence)
