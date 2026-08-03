"""Build analysis context summaries for master commentary."""

from stockresearch.core.schemas import (
    DimensionResult,
    HoldingActionOut,
    ResearchReportOut,
    RiskCheckupOut,
)


def _dimension_brief(label: str, dim: DimensionResult) -> str:
    parts = [f"{label} {dim.score}/10"]
    parts.extend(dim.highlights)
    if dim.risks:
        parts.append(f"风险：{'；'.join(dim.risks)}")
    return "。".join(parts)


def build_research_context(report: ResearchReportOut) -> str:
    """Convert a research report into a concise context for master commentary."""
    lines = [
        f"标的：{report.name}({report.symbol})",
        f"综合评分：{report.composite_score}/10，倾向{report.bias}",
        f"结论：{report.summary}",
    ]
    if report.dimensions:
        lines.append("维度评分：")
        for agent_id, dim in report.dimensions.items():
            lines.append(f"- {_dimension_brief(dim.agent or agent_id, dim)}")
    if report.debate:
        lines.append(f"多空分歧：{report.debate.core_divergence}")
        lines.append(f"裁判观点：{report.debate.consensus}")
    if report.news_text_factor:
        lines.append(f"新闻因子：{report.news_text_factor}")
    return "\n".join(lines)


def build_risk_context(result: RiskCheckupOut) -> str:
    """Convert a risk checkup into a concise context for master commentary."""
    lines = [
        f"组合风险等级：{result.llm_analysis.risk_level if result.llm_analysis else '未知'}",
        f"组合结论：{result.portfolio_summary}",
    ]
    if result.llm_analysis:
        llm = result.llm_analysis
        lines.append(f"市场评估：{llm.market_assessment}")
        lines.append(f"相关性分析：{llm.correlation_analysis}")
        lines.append(f"风险叙述：{llm.risk_narrative}")
        if llm.scenario_analysis:
            lines.append(f"情景推演：{'；'.join(llm.scenario_analysis)}")
        if llm.holding_actions:
            lines.append("逐股建议：")
            for action in llm.holding_actions:
                action = (
                    HoldingActionOut.model_validate(action) if isinstance(action, dict) else action
                )
                lines.append(f"- {action.name}({action.symbol})：{action.action}，{action.reason}")
    if result.metrics:
        m = result.metrics
        lines.append(
            f"量化指标：最大回撤{m.max_drawdown:.1%}，年化波动{m.volatility:.1%}，"
            f"夏普{m.sharpe_ratio:.2f}，行业集中度{m.concentration_ratio:.1%}"
        )
    if result.var_result:
        v = result.var_result
        lines.append(
            f"VaR：{v.confidence_level:.0%}置信度 {v.time_horizon_days}天 VaR={v.var_pct:.2%}"
        )
    if result.stress_results:
        lines.append("定量压力情景（相对现价冲击，非历史回放）：")
        for item in result.stress_results[:3]:
            lines.append(f"- {item.name}：损益 {item.pnl:.0f} 元（{item.pnl_pct:.1%}）")
    return "\n".join(lines)


def build_market_context(summary: str) -> str:
    """Build a master commentary context for market-wide analysis."""
    return f"A股市场分析：\n{summary}"
