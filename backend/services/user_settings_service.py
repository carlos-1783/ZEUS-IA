"""Lectura/escritura de preferencias de usuario (fuente de verdad: BD)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_settings import UserSettings

ALLOWED_LANGUAGES = frozenset({"es", "en"})
ALLOWED_THEMES = frozenset({"dark", "light", "auto"})
SESSION_TIMEOUT_MIN = 5
SESSION_TIMEOUT_MAX = 24 * 60


def _defaults_dict() -> Dict[str, Any]:
    return {
        "language": "es",
        "theme": "dark",
        "two_factor_enabled": False,
        "session_timeout": 60,
    }


def get_or_create_user_settings(db: Session, user_id: int) -> UserSettings:
    row = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if row:
        return row
    d = _defaults_dict()
    row = UserSettings(
        user_id=user_id,
        language=d["language"],
        theme=d["theme"],
        two_factor_enabled=d["two_factor_enabled"],
        session_timeout=d["session_timeout"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def settings_to_api(row: UserSettings) -> Dict[str, Any]:
    return {
        "language": row.language,
        "theme": row.theme,
        "two_factor_enabled": bool(row.two_factor_enabled),
        "session_timeout": int(row.session_timeout or 60),
    }


def patch_user_settings(
    db: Session,
    user: User,
    *,
    language: Optional[str] = None,
    theme: Optional[str] = None,
    two_factor_enabled: Optional[bool] = None,
    session_timeout: Optional[int] = None,
) -> UserSettings:
    row = get_or_create_user_settings(db, user.id)
    if language is not None:
        lang = str(language).strip().lower()
        if lang not in ALLOWED_LANGUAGES:
            raise ValueError("language_invalid")
        row.language = lang
    if theme is not None:
        th = str(theme).strip().lower()
        if th not in ALLOWED_THEMES:
            raise ValueError("theme_invalid")
        row.theme = th
    if two_factor_enabled is not None:
        row.two_factor_enabled = bool(two_factor_enabled)
    if session_timeout is not None:
        st = int(session_timeout)
        if st < SESSION_TIMEOUT_MIN or st > SESSION_TIMEOUT_MAX:
            raise ValueError("session_timeout_invalid")
        row.session_timeout = st
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
