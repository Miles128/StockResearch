"""Research report Markdown, PDF, JSON and CSV export."""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path

from stockresearch.core.schemas import DebateResult, DimensionResult, ResearchReportOut

logger = logging.getLogger(__name__)

_BIAS_LABEL = {"bullish": "偏多", "bearish": "偏空", "neutral": "中性"}
_CONF_LABEL = {"high": "高", "medium": "中", "low": "低"}
_FACTOR_STATUS_LABEL = {"verified": "已验证", "partial": "部分验证", "missing": "未验证"}


def _dim_section(key: str, dim: DimensionResult) -> list[str]:
    lines = [
        f"### {dim.agent}（{key}）",
        f"- 评分：**{dim.score}/10** · 置信度：{_CONF_LABEL.get(dim.confidence, dim.confidence)}",
    ]
    if dim.analysis:
        lines.append("")
        lines.append(dim.analysis.strip())
        lines.append("")
    if dim.highlights:
        lines.append("- 亮点：" + "；".join(dim.highlights))
    if dim.risks:
        lines.append("- 风险：" + "；".join(dim.risks))
    if dim.data_sources:
        lines.append("- 数据来源：" + "、".join(dim.data_sources))
    if dim.evidence:
        lines.append("- 证据：")
        for ev in dim.evidence[:6]:
            date = f"（{ev.date}）" if ev.date else ""
            lines.append(f"  - {ev.snippet} · {ev.source}{date}")
    return lines


def _debate_section(debate: DebateResult) -> list[str]:
    lines = [
        "## 多空辩论",
        f"**裁判倾向**：{_BIAS_LABEL.get(debate.final_bias, debate.final_bias)}",
    ]
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


def report_machine_payload(report: ResearchReportOut) -> dict[str, object]:
    """Stable machine-readable snapshot for export / downstream tools."""
    prov = report.bars_provenance
    return {
        "schema": "stockresearch.report.v1",
        "symbol": report.symbol,
        "name": report.name,
        "analysis_depth": report.analysis_depth,
        "composite_score": report.composite_score,
        "composite_confidence": report.composite_confidence,
        "bias": report.bias,
        "summary": report.summary,
        "brief_summary": report.brief_summary,
        "data_gaps": list(report.data_gaps),
        "bars_provenance": (
            {
                "source": prov.source,
                "adjust": prov.adjust,
                "as_of": prov.as_of,
                "partial": prov.partial,
                "note": prov.note,
            }
            if prov is not None
            else None
        ),
        "factors": [
            {
                "key": f.key,
                "label": f.label,
                "value": f.value,
                "percentile": f.percentile,
                "as_of": f.as_of,
                "unit": f.unit,
                "partial": f.partial,
                "note": f.note,
                "bars_source": f.bars_source,
                "bars_adjust": f.bars_adjust,
            }
            for f in report.factors
        ],
        "factor_alignment_note": report.factor_alignment_note,
        "dimension_scores": {
            key: {"score": dim.score, "confidence": dim.confidence, "agent": dim.agent}
            for key, dim in report.dimensions.items()
        },
        "deep_analysis": (
            report.deep_analysis.model_dump() if report.deep_analysis is not None else None
        ),
        "id": report.id,
        "disclaimer": report.disclaimer,
    }


def report_to_json(report: ResearchReportOut, *, indent: int = 2) -> str:
    return json.dumps(report_machine_payload(report), ensure_ascii=False, indent=indent)


def report_to_csv(report: ResearchReportOut) -> str:
    """Flat CSV: one row per numeric factor with report provenance columns."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "symbol",
            "name",
            "analysis_depth",
            "bias",
            "composite_score",
            "bars_adjust",
            "bars_source",
            "bars_as_of",
            "factor_key",
            "factor_label",
            "factor_value",
            "factor_percentile",
            "factor_as_of",
            "factor_unit",
            "factor_partial",
            "factor_bars_adjust",
            "factor_bars_source",
            "factor_note",
        ]
    )
    prov = report.bars_provenance
    bars_adjust = prov.adjust if prov else ""
    bars_source = prov.source if prov else ""
    bars_as_of = prov.as_of if prov else ""
    rows = report.factors or []
    if not rows:
        writer.writerow(
            [
                report.symbol,
                report.name,
                report.analysis_depth,
                report.bias,
                report.composite_score,
                bars_adjust,
                bars_source,
                bars_as_of,
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )
    for f in rows:
        writer.writerow(
            [
                report.symbol,
                report.name,
                report.analysis_depth,
                report.bias,
                report.composite_score,
                bars_adjust,
                bars_source,
                bars_as_of,
                f.key,
                f.label,
                f.value if f.value is not None else "",
                f.percentile if f.percentile is not None else "",
                f.as_of or "",
                f.unit,
                "1" if f.partial else "0",
                f.bars_adjust or "",
                f.bars_source or "",
                f.note or "",
            ]
        )
    return buf.getvalue()


def _impact_section(impact) -> list[str]:
    """深度分析 · 影响 — attribution lines only, no trade verbs."""
    lines = [
        "## 深度分析 · 影响",
        f"- 窗口：{impact.window_trading_days} 个交易日 · 基准：`{impact.market_symbol}` · 模型：`{impact.model}`",
    ]
    if impact.stock_return_pct is not None:
        lines.append(f"- 个股累计：**{impact.stock_return_pct:+.2f}%**")
    if impact.market_contrib_pct is not None:
        lines.append(f"- 市场贡献：{impact.market_contrib_pct:+.2f}%")
    if impact.industry_contrib_pct is not None:
        lines.append(f"- 行业贡献（peer EW 代理）：{impact.industry_contrib_pct:+.2f}%")
    if impact.idio_return_pct is not None:
        lines.append(f"- 特质收益：{impact.idio_return_pct:+.2f}%")
    if impact.r_squared is not None:
        lines.append(f"- β 拟合 R²：{impact.r_squared:.2f}")
    if impact.partial:
        lines.append(f"- partial：{'；'.join(impact.gaps) if impact.gaps else 'yes'}")
    return lines


def _pricing_section(pricing) -> list[str]:
    """深度分析 · 定价桥 — PE/earnings decomposition of recent return.

    Honest-partial: only emits the lines whose values are present; gaps are
    surfaced verbatim so the reader sees what is missing rather than a
    fabricated number.
    """
    lines = ["## 深度分析 · 定价桥"]
    if pricing.window_label:
        lines.append(f"- 窗口：`{pricing.window_label}`")
    if pricing.price_change_pct is not None:
        lines.append(f"- 区间涨跌：**{pricing.price_change_pct:+.2f}%**")
    if pricing.earnings_contrib_pct is not None:
        lines.append(f"- 盈利贡献：{pricing.earnings_contrib_pct:+.2f}%")
    if pricing.multiple_contrib_pct is not None:
        lines.append(f"- 估值贡献（PE 变动）：{pricing.multiple_contrib_pct:+.2f}%")
    if pricing.pe_end is not None:
        lines.append(f"- PE(TTM) 终值：{pricing.pe_end:.2f}")
    if pricing.pe_start is not None:
        lines.append(f"- PE 起点：{pricing.pe_start:.2f}")
    if pricing.implied_growth_pct is not None:
        lines.append(f"- 隐含增长率：{pricing.implied_growth_pct:+.2f}%")
    if pricing.factor_keys_used:
        lines.append(f"- 使用因子：{', '.join(pricing.factor_keys_used)}")
    if pricing.partial:
        lines.append(f"- partial：{'；'.join(pricing.gaps) if pricing.gaps else 'yes'}")
    return lines


def _thesis_section(thesis) -> list[str]:
    """深度分析 · 研究论点 — claim, monitors, invalidate_if, horizon.

    Descriptive only (no trade verbs). Lists are emitted only when non-empty
    so a partial thesis does not produce empty bullets.
    """
    lines = ["## 深度分析 · 研究论点"]
    if thesis.claim:
        lines.append(f"- 论点：{thesis.claim}")
    if thesis.horizon:
        lines.append(f"- 观察窗口：{thesis.horizon}")
    if thesis.evidence_ids:
        lines.append("- 证据：" + " · ".join(thesis.evidence_ids))
    if thesis.monitors:
        lines.append("- 持续监控：")
        for item in thesis.monitors:
            lines.append(f"  - {item}")
    if thesis.invalidate_if:
        lines.append("- 证伪条件：")
        for item in thesis.invalidate_if:
            lines.append(f"  - {item}")
    if thesis.partial:
        lines.append("- partial：yes")
    return lines


def report_to_markdown(report: ResearchReportOut) -> str:
    bias = _BIAS_LABEL.get(report.bias, report.bias)
    conf = _CONF_LABEL.get(report.composite_confidence, report.composite_confidence)
    lines = [
        f"# {report.name}（{report.symbol}）投研报告",
        "",
        f"**加权综合评分**：{report.composite_score}/10 · **倾向**：{bias} · **置信度**：{conf}",
        f"**分析深度**：{report.analysis_depth}",
        "",
        report.summary,
        "",
    ]
    if report.bars_provenance is not None:
        p = report.bars_provenance
        lines.extend(
            [
                "## 日线口径",
                f"- 复权：`{p.adjust}` · 来源：`{p.source}` · as_of：{p.as_of or '—'}"
                + (f" · partial：{p.note or 'yes'}" if p.partial else ""),
                "",
            ]
        )
    if report.factors:
        lines.append("## 数值因子")
        for f in report.factors:
            val = f"{f.value}{f.unit}" if f.value is not None else "—"
            extra = f" · P{round(f.percentile * 100)}" if f.percentile is not None else ""
            partial = " · partial" if f.partial else ""
            lines.append(
                f"- **{f.label}** (`{f.key}`)：{val}{extra}{partial}"
                f" · as_of={f.as_of or '—'} · bars={f.bars_adjust or '—'}/{f.bars_source or '—'}"
            )
        if report.factor_alignment_note:
            lines.append(f"- 对照：{report.factor_alignment_note}")
        lines.append("")
    if report.text_factor_summary:
        lines.extend(["## 文本因子·总结", report.text_factor_summary, ""])
    if report.news_text_factor:
        lines.extend(["## 文本因子·新闻", report.news_text_factor, ""])
    if report.ashare_factors:
        lines.append("## A 股因子检查")
        for factor in report.ashare_factors:
            lines.append(
                f"- **{factor.category}｜{factor.name}**：{_FACTOR_STATUS_LABEL.get(factor.status, factor.status)}"
            )
            if factor.evidence:
                lines.append(f"  - 证据：{'；'.join(factor.evidence)}")
            if factor.missing:
                lines.append(f"  - 缺口：{'；'.join(factor.missing)}")
            if factor.source_details:
                source_text = "；".join(
                    f"{src.layer}/{src.provider}/{src.label}/{src.status}"
                    for src in factor.source_details
                )
                lines.append(f"  - 来源：{source_text}")
        lines.append("")
    dim_count = len(report.dimensions)
    lines.append(f"## 维度分析（{dim_count}）")
    for key, dim in report.dimensions.items():
        lines.extend(_dim_section(key, dim))
        lines.append("")
    if report.debate:
        lines.extend(_debate_section(report.debate))
        lines.append("")
    if report.deep_analysis is not None and report.deep_analysis.impact is not None:
        lines.extend(_impact_section(report.deep_analysis.impact))
        lines.append("")
    if report.deep_analysis is not None and report.deep_analysis.pricing is not None:
        lines.extend(_pricing_section(report.deep_analysis.pricing))
        lines.append("")
    if report.deep_analysis is not None and report.deep_analysis.thesis is not None:
        lines.extend(_thesis_section(report.deep_analysis.thesis))
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
            logger.warning("CJK font load failed for PDF export: %s", font_path, exc_info=True)
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
        chunk = safe if len(safe) <= 1200 else safe[:1199] + "…"
        pdf.multi_cell(width, 7, chunk)

    bias = _BIAS_LABEL.get(report.bias, report.bias)
    conf = _CONF_LABEL.get(report.composite_confidence, report.composite_confidence)
    write_line(f"{report.name}（{report.symbol}）投研报告", size=16, bold=True)
    write_line(f"综合评分：{report.composite_score}/10 · 倾向：{bias} · 置信度：{conf}")
    write_line(f"分析深度：{report.analysis_depth}")
    write_line(report.summary)
    if report.bars_provenance is not None:
        p = report.bars_provenance
        write_line(f"日线口径：{p.adjust}/{p.source} as_of={p.as_of or '—'}", size=10)
    if report.factors:
        write_line("数值因子", size=13, bold=True)
        for f in report.factors[:12]:
            val = f"{f.value}{f.unit}" if f.value is not None else "—"
            write_line(f"{f.label}: {val}")
    if report.ashare_factors:
        write_line("A 股因子检查", size=13, bold=True)
        for factor in report.ashare_factors:
            write_line(
                f"{factor.category}｜{factor.name}：{_FACTOR_STATUS_LABEL.get(factor.status, factor.status)}"
            )
    write_line(f"维度分析（{len(report.dimensions)}）", size=13, bold=True)
    for key, dim in report.dimensions.items():
        write_line(f"{dim.agent}（{key}）— {dim.score}/10", bold=True)
        if dim.analysis:
            write_line(dim.analysis)
        if dim.highlights:
            write_line("亮点：" + "；".join(dim.highlights))
        if dim.risks:
            write_line("风险：" + "；".join(dim.risks))
    if report.debate:
        write_line("多空辩论", size=13, bold=True)
        write_line(
            f"裁判倾向：{_BIAS_LABEL.get(report.debate.final_bias, report.debate.final_bias)}"
        )
        write_line(f"共识：{report.debate.consensus}")
        write_line(f"裁判结论：{report.debate.judge_verdict}")
    if report.leaders:
        write_line("板块龙头简评", size=13, bold=True)
        for ld in report.leaders:
            write_line(f"{ld.name}（{ld.symbol}）{ld.price:.2f} {ld.change_pct:+.2f}%")
            write_line(ld.brief)
    write_line(report.disclaimer, size=9)
    return bytes(pdf.output())
