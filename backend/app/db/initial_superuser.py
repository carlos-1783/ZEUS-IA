import logging
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from app.db.base import SessionLocal
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models.user import User

logger = logging.getLogger("zeus.bootstrap")


def _safe_str(value: Optional[str]) -> str:
    return value.strip() if isinstance(value, str) else ""


def ensure_initial_superuser() -> None:
    """
    Create (or fix) the FIRST_SUPERUSER account defined in settings.

    This runs on every startup so environments that recreate the database
    (Railway, ephemeral deploys, etc.) always end up with at least one
    superuser capable of operating the platform.
    """
    email = _safe_str(settings.FIRST_SUPERUSER_EMAIL)
    password = _safe_str(settings.FIRST_SUPERUSER_PASSWORD)

    if not email or not password:
        logger.warning(
            "[BOOTSTRAP] FIRST_SUPERUSER_EMAIL/PASSWORD not configured. "
            "Skipping automatic superuser creation."
        )
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        hashed_password = get_password_hash(password)

        if not user:
            logger.info("[BOOTSTRAP] Creating initial superuser %s", email)
            user = User(
                email=email,
                full_name="ZEUS Admin",
                hashed_password=hashed_password,
                is_active=True,
                is_superuser=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return

        updated = False
        if not user.is_superuser:
            user.is_superuser = True
            updated = True
        if not user.is_active:
            user.is_active = True
            updated = True
        if not verify_password(password, user.hashed_password):
            user.hashed_password = hashed_password
            updated = True

        if updated:
            logger.info(
                "[BOOTSTRAP] Updating existing superuser %s (flags/password sync)",
                email,
            )
            db.add(user)
            db.commit()

    except SQLAlchemyError as exc:
        logger.error("[BOOTSTRAP] Failed ensuring superuser: %s", exc, exc_info=True)
    finally:
        db.close()

