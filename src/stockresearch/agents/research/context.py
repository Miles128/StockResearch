"""Shared research execution context."""

from dataclasses import dataclass

from stockresearch.agents.research.budget import AnalysisBudget, budget_for_depth
from stockresearch.utils.llm import LLMClient


@dataclass
class ResearchContext:
    symbol: str
    llm: LLMClient
    budget: AnalysisBudget | None = None

    def resolved_budget(self) -> AnalysisBudget:
        return self.budget or budget_for_depth("standard")
