"""J12b R8: modulos_activos ya no se inventa; /system/status expone los modulos reales de la
empresa del usuario (registro company_module_config). Sin LLM ni red."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.user import User


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client():
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def _user(db, company_type=None, superuser=False):
    suf = uuid.uuid4().hex[:8]
    u = User(email=f"j12br8_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="R8", is_active=True, is_superuser=superuser)
    db.add(u)
    db.flush()
    if company_type:
        c = Company(company_name=f"R8 {suf}", slug=f"r8-{suf}", company_type=company_type)
        db.add(c)
        db.flush()
        db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u


def _as(u):
    app.dependency_overrides[get_current_active_user] = lambda: u


def test_system_status_modulos_son_los_reales_de_cada_empresa(db, client):
    bar = _user(db, "bar_restaurant")
    office = _user(db, "office")
    _as(bar)
    m_bar = client.get("/api/v1/system/status").json()["data"]["modulos_activos"]
    _as(office)
    m_off = client.get("/api/v1/system/status").json()["data"]["modulos_activos"]
    assert m_bar["tpv"] is True and m_bar["crm"] is False
    assert m_off["crm"] is True and m_off["tpv"] is False
    assert "modulo1" not in m_bar and "comun" not in m_off


def test_commands_ya_no_inventa_modulos(db, client, tmp_path, monkeypatch):
    from app.core.state_manager import state_manager
    monkeypatch.setattr(state_manager, 'state_file', tmp_path / 's.json')
    su = _user(db, superuser=True)
    _as(su)
    r = client.post("/api/v1/commands/execute", json={"command": "activar:Acme"})
    assert r.status_code == 200
    assert "modulos_activos" not in r.json()["data"]
    r = client.post("/api/v1/commands/execute", json={"command": "estás en casa"})
    assert r.status_code == 200 and "modulos_activos" not in r.json()["data"]
