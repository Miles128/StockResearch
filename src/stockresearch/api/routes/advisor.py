"""Advisor routes — 投顾模式专属接口。

资产配置参考：根据风险等级 + 现金流给出股/债/现金参考配置。
这是教育参考，不是投资指令（PRD §8 合规）。
"""

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from stockresearch.agents.output_style import output_style_scope
from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import llm_from_headers
from stockresearch.core.schemas import AssetAllocationOut, AssetAllocationRequest
from stockresearch.db.models import User
from stockresearch.db.session import get_db
from stockresearch.services.asset_allocation import build_asset_allocation
from stockresearch.utils.llm import LLMClient

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.post("/allocation", response_model=AssetAllocationOut)
async def get_allocation(
    payload: AssetAllocationRequest = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> AssetAllocationOut:
    """根据风险等级 + 现金流给出资产配置参考（投顾模式专属）。"""
    with output_style_scope(
        reading_mode=payload.reading_mode,
        locale=payload.output_locale,
    ):
        return await build_asset_allocation(
            risk_tolerance=payload.risk_tolerance,
            monthly_income=payload.monthly_income,
            llm=llm,
        )
