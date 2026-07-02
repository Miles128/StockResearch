"""Industry research entry — collects Research Stream result for sync callers."""

from sqlalchemy.orm import Session

from stockresearch.agents.industry.stream import run_industry_research_stream
from stockresearch.core.schemas import ModeSettingsOut, ResearchReportOut
from stockresearch.utils.llm import LLMClient


async def run_industry_research(
    db: Session,
    llm: LLMClient,
    user_id: int,
    sector: str,
    message: str,
    *,
    with_debate: bool = False,
    enable_master_commentary: bool = False,
    mode_settings: ModeSettingsOut | None = None,
) -> tuple[str, list[dict[str, object]]]:
    report: ResearchReportOut | None = None
    async for event in run_industry_research_stream(
        db,
        user_id,
        sector,
        message,
        llm,
        with_debate=with_debate,
        enable_master_commentary=enable_master_commentary,
        mode_settings=mode_settings,
    ):
        if event.get("type") == "done":
            raw = event.get("result")
            if isinstance(raw, dict):
                report = ResearchReportOut.model_validate(raw)

    if report is None:
        return "板块投研暂时无法完成，请稍后重试。", []

    cards: list[dict[str, object]] = [
        {"type": "research", "data": report.model_dump(mode="json")},
    ]
    if report.leaders:
        cards.append(
            {
                "type": "text",
                "data": {
                    "content": "\n".join(
                        f"**{ld.name}({ld.symbol})** {ld.change_pct:+.2f}% — {ld.brief}"
                        for ld in report.leaders
                    ),
                },
            }
        )
    return report.summary, cards
