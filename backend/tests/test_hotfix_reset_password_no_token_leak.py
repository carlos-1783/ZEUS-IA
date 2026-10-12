"""HOTFIX — /auth/reset-password devolvia el enlace con el token en la respuesta HTTP.

Con solo el email de la victima, una peticion anonima obtenia el token y POST
/auth/new-password fijaba una contrasena nueva (toma de cualquier cuenta, incluida la de
superusuario). Ahora el enlace solo se envia por correo al titular.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash, verify_password
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.user import PasswordResetToken, User

P = "/api/v1/auth"


@pytest.fixture()
def victim():
    Base.metadata.create_all(bind=engine, tables=[User.__table__, PasswordResetToken.__table__])
    db = SessionLocal()
    email = f"victima{uuid.uuid4().hex[:8]}@example.com"
    db.add(User(email=email, hashed_password=get_password_hash("ClaveOriginal1"), is_active=True, is_superuser=True))
    db.commit()
    try:
        yield db, email
    finally:
        db.close()


def _stored_token(db, email):
    db.expire_all()
    row = db.query(PasswordResetToken).filter(PasswordResetToken.email == email).first()
    return row.token if row else None


def test_response_never_contains_the_token(victim):
    db, email = victim
    r = TestClient(app).post(f"{P}/reset-password", json={"email": email})
    assert r.status_code == 200
    token = _stored_token(db, email)
    assert token, "el token se sigue generando para el enlace del correo"
    assert set(r.json()) == {"msg"}
    assert token not in r.text


def test_unknown_and_known_email_get_identical_response(victim):
    _, email = victim
    c = TestClient(app)
    known = c.post(f"{P}/reset-password", json={"email": email}).json()
    unknown = c.post(f"{P}/reset-password", json={"email": f"nadie{uuid.uuid4().hex[:6]}@example.com"}).json()
    assert known == unknown


def test_attacker_cannot_take_over_account(victim):
    db, email = victim
    c = TestClient(app)
    body = c.post(f"{P}/reset-password", json={"email": email}).json()
    leaked = (body.get("reset_link") or "").rsplit("/", 1)[-1]
    r = c.post(f"{P}/new-password", json={"token": leaked or "x" * 43, "new_password": "Atacante123!x"})
    assert r.status_code == 400
    db.expire_all()
    u = db.query(User).filter(User.email == email).first()
    assert verify_password("ClaveOriginal1", u.hashed_password)


def test_link_is_emailed_only_to_the_account_owner(victim):
    db, email = victim
    from services.email_service import email_service

    with patch.object(email_service, "is_smtp_configured", return_value=True), patch.object(
        email_service, "send_email", new=AsyncMock(return_value={"success": True})
    ) as send:
        r = TestClient(app).post(f"{P}/reset-password", json={"email": email})
    assert r.status_code == 200 and "reset_link" not in r.json()
    send.assert_awaited_once()
    kwargs = send.await_args.kwargs
    assert kwargs["to_email"] == email
    assert _stored_token(db, email) in kwargs["content"]
