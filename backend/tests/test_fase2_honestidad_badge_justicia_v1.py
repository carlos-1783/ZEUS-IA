"""Fase 2 / honestidad final #26 — /justicia/v1/system-audit con el flag apagado: badge
DESACTIVADO (no se ejecuta nada), no SIMULADO."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.user import User


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Jb {suf}", slug=f"jb-{suf}")
    u = User(email=f"jb_{suf}@example.test", hashed_password=get_password_hash("TestPass1"), is_active=True)
    s.add_all([c, u])
    s.flush()
    s.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    s.commit()
    s.refresh(u)
    app.dependency_overrides[get_current_active_user] = lambda: u
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
        s.close()


def test_flag_apagado_desactivado(client, monkeypatch):
    monkeypatch.setattr(settings, "JUSTICE_REAL_AUDIT_ENABLED", False, raising=False)
    r = client.get("/api/v1/justicia/v1/system-audit")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["real_execution"] is False
    assert b["justicia_control"]["ui_badge"] == "DESACTIVADO"


def test_flag_encendido_real(client, monkeypatch):
    monkeypatch.setattr(settings, "JUSTICE_REAL_AUDIT_ENABLED", True, raising=False)
    r = client.get("/api/v1/justicia/v1/system-audit")
    assert r.status_code == 200, r.text
    assert r.json()["justicia_control"]["ui_badge"] == "REAL"
