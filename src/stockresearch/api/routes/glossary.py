"""Glossary routes — expose term dictionary for frontend click-to-show popovers."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.db.models import User
from stockresearch.db.session import get_db
from stockresearch.services.glossary import list_glossary_payload
from stockresearch.services.user_preferences import get_mode_settings

router = APIRouter(prefix="/glossary", tags=["glossary"])


@router.get("")
def list_glossary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, str | bool]]:
    """返回内置 + 用户自定义词库，供设置页与 TermPopover 使用。"""
    settings = get_mode_settings(db, user.id)
    return list_glossary_payload(settings.custom_glossary)
