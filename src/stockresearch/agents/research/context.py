"""Shared research execution context."""

from dataclasses import dataclass

from stockresearch.utils.llm import LLMClient


@dataclass
class ResearchContext:
    symbol: str
    llm: LLMClient
