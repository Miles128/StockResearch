"""Registry of independent ReAct dimension agents."""

from stockresearch.agents.research.agents.chips import CHIPS_AGENT
from stockresearch.agents.research.agents.fundamental import FUNDAMENTAL_AGENT
from stockresearch.agents.research.agents.sentiment import SENTIMENT_AGENT
from stockresearch.agents.research.agents.technical import TECHNICAL_AGENT
from stockresearch.agents.research.react import DimensionAgent

DIMENSION_AGENTS: tuple[DimensionAgent, ...] = (
    FUNDAMENTAL_AGENT,
    TECHNICAL_AGENT,
    SENTIMENT_AGENT,
    CHIPS_AGENT,
)

AGENT_BY_ID: dict[str, DimensionAgent] = {agent.agent_id: agent for agent in DIMENSION_AGENTS}
