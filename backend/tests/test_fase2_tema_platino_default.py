"""Fase 2 / JARVIS: un usuario nuevo arranca en tema PLATINO ('light'), no en oscuro."""

from __future__ import annotations

import uuid

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.user import User
from services.user_settings_service import get_or_create_user_settings


def test_new_user_settings_default_to_platino():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        u = User(email=f"tema_{uuid.uuid4().hex[:8]}@example.com",
                 hashed_password=get_password_hash("TestPass1"), is_active=True)
        db.add(u)
        db.commit()
        row = get_or_create_user_settings(db, u.id)
        assert row.theme == "light"
    finally:
        db.close()
