"""Local single-user preference persistence."""

import logging

from sqlalchemy.orm import Session

from stockresearch.core.schemas import ModeSettingsOut, ModeSettingsUpdate
from stockresearch.db.models import UserPreference

logger = logging.getLogger(__name__)

DEFAULT_MODE_SETTINGS = ModeSettingsOut()


def _coerce_mode_settings(raw: object) -> ModeSettingsOut:
    if not isinstance(raw, dict):
        return DEFAULT_MODE_SETTINGS.model_copy()
    data = dict(raw)
    if "analysis_depth" not in data:
        from stockresearch.agents.research.budget import default_depth_for_mode

        data["analysis_depth"] = default_depth_for_mode(str(data.get("mode") or "advisor"))
    try:
        return ModeSettingsOut.model_validate(data)
    except Exception:
        logger.warning("invalid mode_settings; using defaults", exc_info=True)
        return DEFAULT_MODE_SETTINGS.model_copy()


def get_mode_settings(db: Session, user_id: int) -> ModeSettingsOut:
    preference = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if preference is None:
        settings = DEFAULT_MODE_SETTINGS.model_copy()
    else:
        settings = _coerce_mode_settings(preference.mode_settings)
    if settings.mode == "research":
        settings = settings.model_copy(update={"enable_glossary": False})
    return settings


def save_mode_settings(
    db: Session,
    user_id: int,
    payload: ModeSettingsUpdate,
) -> ModeSettingsOut:
    data = payload.model_dump()
    if data.get("mode") == "research":
        data["enable_glossary"] = False
    preference = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if preference is None:
        preference = UserPreference(user_id=user_id, mode_settings=data)
        db.add(preference)
    else:
        preference.mode_settings = data
    db.commit()
    db.refresh(preference)
    saved = _coerce_mode_settings(preference.mode_settings)
    if saved.mode == "research":
        saved = saved.model_copy(update={"enable_glossary": False})
    return saved
