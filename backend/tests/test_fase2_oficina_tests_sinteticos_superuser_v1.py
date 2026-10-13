"""Fase 2 / Analiticas — los flujos de prueba con payload sintetico (/test/contract-flow,
/test/payment-risk) ya no los puede lanzar un cliente sobre su propia cuenta."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.user import User
from app.models.zeus_analytics import ZeusAutomationLog


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _auth(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'email': u.email})}"}


def _user(db, superuser=False):
    suf = uuid.uuid4().hex[:8]
    u = User(email=f"syn_{suf}@example.com", hashed_password=get_password_hash("TestPass1"),
             is_active=True, is_superuser=superuser)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.mark.parametrize("path", ["/api/v1/test/contract-flow", "/api/v1/test/payment-risk"])
def test_without_credentials_rejected(path):
    assert TestClient(app).post(path, json={}).status_code in (401, 403)


@pytest.mark.parametrize("path", ["/api/v1/test/contract-flow", "/api/v1/test/payment-risk"])
def test_client_cannot_inject_synthetic_flows(db, path):
    u = _user(db)
    r = TestClient(app).post(path, json={}, headers=_auth(u))
    assert r.status_code == 403
    db.expire_all()
    assert db.query(ZeusAutomationLog).filter(ZeusAutomationLog.user_id == u.id).count() == 0


@pytest.mark.parametrize(
    "path,target",
    [
        ("/api/v1/test/contract-flow", "run_test_contract_flow"),
        ("/api/v1/test/payment-risk", "run_test_payment_risk_flow"),
    ],
)
def test_superuser_can_run(db, monkeypatch, path, target):
    from app.api.v1.endpoints import test as ep

    su = _user(db, superuser=True)
    monkeypatch.setattr(ep, target, lambda db, user: {"success": True, "triggered": False, "who": user.id})
    r = TestClient(app).post(path, json={}, headers=_auth(su))
    assert r.status_code == 200 and r.json()["who"] == su.id
