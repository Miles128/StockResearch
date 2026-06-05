"""Research report Markdown export."""

from stockresearch.core.schemas import DebateResult, DimensionResult, ResearchReportOut

_BIAS_LABEL = {"bullish": "偏多", "bearish": "偏空", "neutral": "中性"}
_CONF_LABEL = {"high": "高", "medium": "中", "low": "低"}


def _dim_section(key: str, dim: DimensionResult) -> list[str]:
    lines = [
        f"### {dim.agent}（{key}）",
        f"- 评分：**{dim.score}/10** · 置信度：{_CONF_LABEL.get(dim.confidence, dim.confidence)}",
    ]
    if dim.highlights:
        lines.append("- 亮点：" + "；".join(dim.highlights))
    if dim.risks:
        lines.append("- 风险：" + "；".join(dim.risks))
    if dim.data_sources:
        lines.append("- 数据来源：" + "、".join(dim.data_sources))
    return lines


def _debate_section(debate: DebateResult) -> list[str]:
    lines = ["## 多空辩论", f"**裁判倾向**：{_BIAS_LABEL.get(debate.final_bias, debate.final_bias)}"]
    lines.append(f"- 共识：{debate.consensus}")
    lines.append(f"- 核心分歧：{debate.core_divergence}")
    if debate.vote_tally:
        tally = debate.vote_tally
        lines.append(
            f"- 投票：偏多 {tally.get('偏多', 0)} · 偏空 {tally.get('偏空', 0)} · 中性 {tally.get('中性', 0)}"
        )
    if debate.manager_thesis:
        lines.append(f"- Research Manager：{debate.manager_thesis}")
    for rnd in debate.rounds:
        lines.append(f"### 第 {rnd.round} 轮")
        lines.append(f"**看多**：{rnd.bull_argument}")
        lines.append(f"**看空**：{rnd.bear_rebuttal}")
    lines.append(f"**裁判结论**：{debate.judge_verdict}")
    return lines


def report_to_markdown(report: ResearchReportOut) -> str:
    bias = _BIAS_LABEL.get(report.bias, report.bias)
    conf = _CONF_LABEL.get(report.composite_confidence, report.composite_confidence)
    lines = [
        f"# {report.name}（{report.symbol}）投研报告",
        "",
        f"**综合评分**：{report.composite_score}/10 · **倾向**：{bias} · **置信度**：{conf}",
        "",
        report.summary,
        "",
        "## 四维分析",
    ]
    for key, dim in report.dimensions.items():
        lines.extend(_dim_section(key, dim))
        lines.append("")
    if report.debate:
        lines.extend(_debate_section(report.debate))
        lines.append("")
    lines.append("---")
    lines.append(report.disclaimer)
    return "\n".join(lines)
