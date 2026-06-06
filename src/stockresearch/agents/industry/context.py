"""Sector research execution context."""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from stockresearch.data.providers.sector import SectorBoard, SectorLeader
from stockresearch.utils.llm import LLMClient


@dataclass
class SectorResearchContext:
    sector: str
    query: str
    llm: LLMClient
    user_id: int
    db: Session
    board: SectorBoard | None = None
    leaders: list[SectorLeader] = field(default_factory=list)
    news_snippets: list[str] = field(default_factory=list)
    holding_lines: list[str] = field(default_factory=list)
