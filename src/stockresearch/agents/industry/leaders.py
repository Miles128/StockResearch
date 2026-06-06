"""Lightweight leader-stock analysis within a sector."""

from collections.abc import AsyncIterator

from stockresearch.agents.industry.context import SectorResearchContext
from stockresearch.agents.stream_typewriter import iter_llm_stream_events
from stockresearch.agents.voice import AGENT_VOICE
from stockresearch.core.schemas import SectorLeaderBrief
from stockresearch.data.providers.market import QuoteProvider
from stockresearch.data.providers.sector import SectorLeader

_LEADER_SYSTEM = f"""你是 A 股板块龙头分析师。{AGENT_VOICE}
用 2-3 句话简述该股在板块中的地位、短线强弱与主要风险。不要给出买卖建议。"""


async def _quote_for(leader: SectorLeader) -> tuple[float, float]:
    if not leader.symbol:
        return 0.0, leader.change_pct
    try:
        q = await QuoteProvider().get_quote(leader.symbol)
        return q.price, q.change_pct
    except Exception:
        return 0.0, leader.change_pct


async def iter_leader_analysis_events(
    ctx: SectorResearchContext,
    leaders: list[SectorLeader],
    *,
    limit: int = 3,
) -> AsyncIterator[dict[str, object]]:
    """Stream brief leader analysis as SSE events."""
    briefs: list[SectorLeaderBrief] = []
    for idx, leader in enumerate(leaders[:limit], start=1):
        price, change_pct = await _quote_for(leader)
        agent_id = f"leader_{leader.symbol or idx}"
        yield {
            "type": "agent_start",
            "agent_id": agent_id,
            "agent_name": f"龙头·{leader.name}",
            "role": "analyst",
        }
        user = (
            f"板块：{ctx.sector}\n"
            f"个股：{leader.name}({leader.symbol})\n"
            f"现价：{price:.2f} 涨跌：{change_pct:+.2f}%\n"
            f"角色：{'板块领涨' if leader.role == 'board_leader' else '代表股'}"
        )
        content = ""
        async for event in iter_llm_stream_events(
            stream_id=agent_id,
            agent_id=agent_id,
            agent_name=f"龙头·{leader.name}",
            role="analyst",
            llm=ctx.llm,
            system=_LEADER_SYSTEM,
            user=user,
        ):
            yield event
            if event.get("type") == "agent_done":
                content = str(event.get("content", ""))
        briefs.append(
            SectorLeaderBrief(
                symbol=leader.symbol,
                name=leader.name,
                price=price,
                change_pct=change_pct,
                brief=content.strip() or f"{leader.name} 暂缺简评。",
            )
        )
    yield {"type": "leader_briefs", "leaders": [b.model_dump(mode="json") for b in briefs]}


async def analyze_sector_leaders(
    ctx: SectorResearchContext,
    leaders: list[SectorLeader],
    *,
    limit: int = 3,
) -> list[SectorLeaderBrief]:
    collected: list[SectorLeaderBrief] = []
    async for event in iter_leader_analysis_events(ctx, leaders, limit=limit):
        if event.get("type") == "leader_briefs":
            raw = event.get("leaders", [])
            if isinstance(raw, list):
                collected = [SectorLeaderBrief.model_validate(item) for item in raw]
    return collected
