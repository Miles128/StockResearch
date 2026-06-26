"""Local single-user preference persistence."""

from sqlalchemy.orm import Session

from stockresearch.core.schemas import ModeSettingsOut, ModeSettingsUpdate
from stockresearch.db.models import UserPreference

DEFAULT_MODE_SETTINGS = ModeSettingsOut()


def _coerce_mode_settings(raw: object) -> ModeSettingsOut:
    if not isinstance(raw, dict):
        return DEFAULT_MODE_SETTINGS.model_copy()
    try:
        return ModeSettingsOut.model_validate(raw)
    except Exception:
        return DEFAULT_MODE_SETTINGS.model_copy()


def get_mode_settings(db: Session, user_id: int) -> ModeSettingsOut:
    preference = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if preference is None:
        return DEFAULT_MODE_SETTINGS.model_copy()
    return _coerce_mode_settings(preference.mode_settings)


def save_mode_settings(
    db: Session,
    user_id: int,
    payload: ModeSettingsUpdate,
) -> ModeSettingsOut:
    data = payload.model_dump()
    preference = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if preference is None:
        preference = UserPreference(user_id=user_id, mode_settings=data)
        db.add(preference)
    else:
        preference.mode_settings = data
    db.commit()
    db.refresh(preference)
    return _coerce_mode_settings(preference.mode_settings)
