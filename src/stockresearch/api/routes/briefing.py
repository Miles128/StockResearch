"""Portfolio briefing routes."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import llm_from_headers
from stockresearch.core.schemas import BriefingOut
from stockresearch.db.models import User
from stockresearch.db.session import get_db
from stockresearch.services.briefing import generate_briefing
from stockresearch.utils.llm import LLMClient

router = APIRouter(prefix="/briefing", tags=["briefing"])


@router.post("/generate", response_model=BriefingOut)
async def generate_portfolio_briefing(
    kind: Literal["morning", "closing"] = Query(default="morning"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> BriefingOut:
    return await generate_briefing(db, user.id, kind, llm=llm)
