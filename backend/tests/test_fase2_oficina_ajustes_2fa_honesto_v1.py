"""Fase 2 / Ajustes — la "verificacion en dos pasos" no se puede activar mientras no exista
el flujo real en el login (antes se guardaba y aparentaba proteger la cuenta)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.user import User
from services import user_settings_service as uss

P = "/api/v1/settings"


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _user(db):
    suf = uuid.uuid4().hex[:8]
    u = User(email=f"set_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'email': u.email})}"}


def test_enable_2fa_is_blocked_honestly(db):
    u = _user(db)
    c = TestClient(app)
    r = c.patch(P, json={"two_factor_enabled": True}, headers=_h(u))
    assert r.status_code == 501
    assert "dos pasos" in r.json()["detail"]
    db.expire_all()
    row = uss.get_or_create_user_settings(db, u.id)
    assert not row.two_factor_enabled


def test_get_reports_real_state_even_if_stored_true(db):
    u = _user(db)
    row = uss.get_or_create_user_settings(db, u.id)
    row.two_factor_enabled = True  # valor heredado de antes del bloqueo
    db.commit()
    r = TestClient(app).get(P, headers=_h(u))
    assert r.status_code == 200 and r.json()["two_factor_enabled"] is False


def test_other_settings_still_persist_per_user(db):
    me, other = _user(db), _user(db)
    c = TestClient(app)
    assert c.patch(P, json={"theme": "dark", "session_timeout": 120}, headers=_h(other)).status_code == 200
    r = c.patch(P, json={"theme": "light", "session_timeout": 30}, headers=_h(me))
    assert r.status_code == 200 and r.json()["theme"] == "light"
    mine, theirs = c.get(P, headers=_h(me)).json(), c.get(P, headers=_h(other)).json()
    assert (mine["theme"], mine["session_timeout"]) == ("light", 30)
    assert (theirs["theme"], theirs["session_timeout"]) == ("dark", 120)


def test_settings_require_auth():
    assert TestClient(app).patch(P, json={"theme": "light"}).status_code in (401, 403)
