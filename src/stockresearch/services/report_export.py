"""Research report Markdown and PDF export."""

from pathlib import Path

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
        f"**加权综合评分**：{report.composite_score}/10 · **倾向**：{bias} · **置信度**：{conf}",
        "",
        report.summary,
        "",
    ]
    if report.text_factor_summary:
        lines.extend(["## 文本因子·总结", report.text_factor_summary, ""])
    if report.news_text_factor:
        lines.extend(["## 文本因子·新闻", report.news_text_factor, ""])
    lines.append("## 四维分析")
    for key, dim in report.dimensions.items():
        lines.extend(_dim_section(key, dim))
        lines.append("")
    if report.debate:
        lines.extend(_debate_section(report.debate))
        lines.append("")
    if report.leaders:
        lines.append("## 板块龙头简评")
        for ld in report.leaders:
            lines.append(f"### {ld.name}（{ld.symbol}）")
            lines.append(f"- 现价 {ld.price:.2f} · 涨跌 {ld.change_pct:+.2f}%")
            lines.append(f"- {ld.brief}")
        lines.append("")
    if report.sector:
        lines.insert(2, f"**板块**：{report.sector}")
    lines.append("---")
    lines.append(report.disclaimer)
    return "\n".join(lines)


def _resolve_cjk_font() -> Path | None:
    candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("C:/Windows/Fonts/msyh.ttc"),
    ]
    for path in candidates:
        if path.is_file() and path.suffix.lower() in {".ttf", ".otf"}:
            return path
    return None


def report_to_pdf(report: ResearchReportOut) -> bytes:
    from fpdf import FPDF

    font_path = _resolve_cjk_font()
    pdf = FPDF()
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    use_cjk = False
    if font_path:
        try:
            pdf.add_font("CJK", "", str(font_path))
            use_cjk = True
        except Exception:
            use_cjk = False

    def write_line(text: str, *, size: int = 11, bold: bool = False) -> None:
        if use_cjk:
            pdf.set_font("CJK", size=size)
            safe = text
        else:
            style = "B" if bold else ""
            pdf.set_font("Helvetica", style=style, size=size)
            safe = text.encode("ascii", "replace").decode("ascii")
        width = pdf.epw if pdf.epw > 0 else 180
        pdf.multi_cell(width, 7, safe)

    bias = _BIAS_LABEL.get(report.bias, report.bias)
    conf = _CONF_LABEL.get(report.composite_confidence, report.composite_confidence)
    write_line(f"{report.name}（{report.symbol}）投研报告", size=16, bold=True)
    write_line(f"综合评分：{report.composite_score}/10 · 倾向：{bias} · 置信度：{conf}")
    write_line(report.summary)
    write_line("四维分析", size=13, bold=True)
    for key, dim in report.dimensions.items():
        write_line(f"{dim.agent}（{key}）— {dim.score}/10", bold=True)
        if dim.highlights:
            write_line("亮点：" + "；".join(dim.highlights))
        if dim.risks:
            write_line("风险：" + "；".join(dim.risks))
    if report.debate:
        write_line("多空辩论", size=13, bold=True)
        write_line(f"裁判倾向：{_BIAS_LABEL.get(report.debate.final_bias, report.debate.final_bias)}")
        write_line(f"共识：{report.debate.consensus}")
        write_line(f"裁判结论：{report.debate.judge_verdict}")
    if report.leaders:
        write_line("板块龙头简评", size=13, bold=True)
        for ld in report.leaders:
            write_line(f"{ld.name}（{ld.symbol}）{ld.price:.2f} {ld.change_pct:+.2f}%")
            write_line(ld.brief)
    write_line(report.disclaimer, size=9)
    return bytes(pdf.output())
