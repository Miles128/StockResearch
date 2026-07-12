"""Shared parsing and voice for dimension research chapters."""

from __future__ import annotations

import re
from typing import Literal

from stockresearch.core.schemas import DimensionEvidence, DimensionResult

REPORT_DIM_VOICE = (
    "按研究报告章节撰写，禁止 markdown，不要建议买卖。"
    "严格使用下列标记，顺序不可乱：\n"
    "【分析】用 4～8 句写清现状、关键数据含义与判断（约 180～400 字）；\n"
    "【亮点】2～4 条短句，用分号分隔；\n"
    "【风险】1～3 条短句，用分号分隔。"
)

_SECTION_RE = re.compile(
    r"【\s*(分析|亮点|风险)\s*】\s*(.*?)(?=【\s*(?:分析|亮点|风险)\s*】|$)",
    re.DOTALL,
)


def _split_bullets(text: str, *, limit: int) -> list[str]:
    raw = text.replace("\n", "；").replace("、", "；")
    parts = [p.strip(" ；。.") for p in re.split(r"[；;•·]+", raw) if p.strip(" ；。.")]
    return parts[:limit]


def parse_dimension_analysis(raw: str) -> tuple[str, list[str], list[str]]:
    """Parse marked LLM output into analysis / highlights / risks."""
    text = (raw or "").strip()
    if not text:
        return "", [], []

    sections: dict[str, str] = {}
    for match in _SECTION_RE.finditer(text):
        key = match.group(1).strip()
        sections[key] = match.group(2).strip()

    if sections:
        analysis = sections.get("分析", "").strip()
        highlights = _split_bullets(sections.get("亮点", ""), limit=4)
        risks = _split_bullets(sections.get("风险", ""), limit=3)
        if not analysis:
            # Marked but empty analysis — fall back to unmarked remainder.
            analysis = _SECTION_RE.sub("", text).strip() or text
        return analysis, highlights, risks

    # No markers: whole text is the chapter; heuristic bullets.
    analysis = text
    highlights = [
        line.strip(" ；。")
        for line in text.replace("！", "。").split("。")
        if line.strip() and ("亮点" in line or "增长" in line or "流入" in line)
    ][:3]
    risks = [
        line.strip(" ；。")
        for line in text.replace("！", "。").split("。")
        if line.strip() and ("风险" in line or "压力" in line or "回撤" in line)
    ][:3]
    return analysis, highlights, risks


def finalize_dimension(
    *,
    agent: str,
    score: float,
    confidence: Literal["high", "medium", "low"],
    raw_analysis: str,
    data_sources: list[str],
    fallback_highlights: list[str] | None = None,
    fallback_risks: list[str] | None = None,
    evidence: list[DimensionEvidence] | None = None,
    gaps: list[str] | None = None,
    partial: bool = False,
) -> DimensionResult:
    analysis, highlights, risks = parse_dimension_analysis(raw_analysis)
    if not highlights:
        highlights = [h for h in (fallback_highlights or []) if h and h.strip()][:4]
    if not risks:
        risks = [r for r in (fallback_risks or []) if r and r.strip()][:3]
    if not analysis and highlights:
        analysis = "。".join(highlights)
        if analysis and not analysis.endswith("。"):
            analysis += "。"
    return DimensionResult(
        agent=agent,
        score=round(score, 1),
        confidence=confidence,
        analysis=analysis,
        highlights=highlights or (["数据有限，结论仅供参考"] if not analysis else []),
        risks=risks or ["需结合更多公开信息交叉验证"],
        data_sources=data_sources,
        evidence=evidence or [],
        gaps=(gaps or [])[:8],
        partial=partial,
    )


def build_brief_summary(
    *,
    name: str,
    symbol: str,
    bias: Literal["bullish", "bearish", "neutral"],
    composite_score: float,
    dimensions: dict[str, DimensionResult],
    dimension_labels: dict[str, str],
) -> str:
    """Plain-language one-paragraph brief for personal (advisor) UI."""
    bias_plain = {"bullish": "整体偏乐观", "bearish": "整体偏谨慎", "neutral": "整体偏中性"}[bias]
    score_plain = f"综合大约 {composite_score:.1f} 分（满分 10）"
    bits: list[str] = [f"{name}（{symbol}）{bias_plain}，{score_plain}。"]
    for key, dim in dimensions.items():
        label = dimension_labels.get(key) or dim.agent or key
        tip = (dim.highlights[0] if dim.highlights else "").strip().rstrip("。")
        if not tip and dim.analysis:
            tip = dim.analysis.split("。")[0].strip()
        if tip:
            bits.append(f"{label}看：{tip}。")
        if len(bits) >= 5:
            break
    return "".join(bits)
