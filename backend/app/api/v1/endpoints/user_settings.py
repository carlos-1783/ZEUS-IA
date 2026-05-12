"""GET/PATCH /settings — preferencias persistidas por usuario."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services import user_settings_service as uss

logger = logging.getLogger(__name__)

router = APIRouter()


class UserSettingsResponse(BaseModel):
    language: str
    theme: str
    two_factor_enabled: bool
    session_timeout: int


class UserSettingsPatchBody(BaseModel):
    language: Optional[str] = Field(None, description="es | en")
    theme: Optional[str] = Field(None, description="dark | light | auto")
    two_factor_enabled: Optional[bool] = None
    session_timeout: Optional[int] = Field(None, ge=uss.SESSION_TIMEOUT_MIN, le=uss.SESSION_TIMEOUT_MAX)


@router.get("", response_model=UserSettingsResponse)
def get_user_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    row = uss.get_or_create_user_settings(db, current_user.id)
    out = uss.settings_to_api(row)
    logger.info("GET /settings user_id=%s payload=%s", current_user.id, out)
    return out


@router.patch("", response_model=UserSettingsResponse)
def patch_user_settings_endpoint(
    body: UserSettingsPatchBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    if not data:
        row = uss.get_or_create_user_settings(db, current_user.id)
        return uss.settings_to_api(row)
    try:
        row = uss.patch_user_settings(
            db,
            current_user,
            language=data.get("language"),
            theme=data.get("theme"),
            two_factor_enabled=data.get("two_factor_enabled"),
            session_timeout=data.get("session_timeout"),
        )
    except ValueError as e:
        code = str(e)
        if code == "language_invalid":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idioma no válido (use es o en).")
        if code == "theme_invalid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tema no válido (dark, light o auto).",
            )
        if code == "session_timeout_invalid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"session_timeout debe estar entre {uss.SESSION_TIMEOUT_MIN} y {uss.SESSION_TIMEOUT_MAX} minutos.",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Datos no válidos")
    out = uss.settings_to_api(row)
    logger.info("PATCH /settings user_id=%s body=%s result=%s", current_user.id, data, out)
    return out
