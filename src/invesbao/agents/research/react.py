"""Lightweight ReAct runner — each dimension agent owns an isolated toolset."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from invesbao.agents.research.context import ResearchContext
from invesbao.core.schemas import DimensionResult

ToolFn = Callable[[ResearchContext], Awaitable[dict[str, object]]]
BuildFn = Callable[[dict[str, object], str], DimensionResult]


@dataclass(frozen=True)
class ResearchTool:
    name: str
    description: str
    run: ToolFn


@dataclass(frozen=True)
class DimensionAgent:
    agent_id: str
    label: str
    system_prompt: str
    tools: tuple[ResearchTool, ...]
    build: BuildFn

    @property
    def data_sources(self) -> list[str]:
        return [tool.name for tool in self.tools]


async def execute_tools(
    ctx: ResearchContext,
    tools: tuple[ResearchTool, ...],
) -> dict[str, object]:
    observations: dict[str, object] = {}
    for tool in tools:
        observations[tool.name] = await tool.run(ctx)
    return observations


def format_observations(observations: dict[str, object]) -> str:
    lines: list[str] = []
    for name, payload in observations.items():
        lines.append(f"[{name}] {payload}")
    return "\n".join(lines)


async def run_react_agent(agent: DimensionAgent, ctx: ResearchContext) -> DimensionResult:
    """Gather tool outputs, then LLM synthesizes — one ReAct cycle."""
    observations = await execute_tools(ctx, agent.tools)
    user = format_observations(observations)
    analysis = await ctx.llm.complete(agent.system_prompt, user)
    return agent.build(observations, analysis)


async def prepare_react_agent(
    agent: DimensionAgent,
    ctx: ResearchContext,
) -> tuple[str, str, dict[str, object]]:
    observations = await execute_tools(ctx, agent.tools)
    return agent.system_prompt, format_observations(observations), observations
