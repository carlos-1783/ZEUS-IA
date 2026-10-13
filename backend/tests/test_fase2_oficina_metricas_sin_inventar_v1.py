"""Fase 2 / Panel — /metrics/summary y /metrics/dashboard sin cifras inventadas
(ahorro = exitos x 50 EUR, tendencia contra 96 % fijo) y sin mezclar cuentas."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.user import User
from app.api.v1.endpoints.metrics import _real_trends


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
    c = Company(company_name=f"M {suf}", slug=f"m-{suf}")
    u = User(email=f"met_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'email': u.email})}"}


def _act(u, cid, status="completed", days_ago=1):
    t = datetime.utcnow() - timedelta(days=days_ago)
    return AgentActivity(agent_name="PERSEO", action_type="x", action_description="t", status=status,
                         user_email=u.email, company_id=cid, created_at=t, completed_at=t + timedelta(seconds=2))


def test_summary_has_no_invented_savings_and_is_tenant_scoped(db):
    me, cme = _user(db)
    other, cother = _user(db)
    db.add_all([_act(me, cme.id), _act(me, cme.id), _act(me, cme.id, status="failed")]
               + [_act(other, cother.id) for _ in range(5)])
    db.commit()
    r = TestClient(app).get("/api/v1/metrics/summary?days=30", headers=_h(me))
    assert r.status_code == 200
    m = r.json()["metrics"]
    assert m["total_interactions"] == 3  # solo las de mi cuenta, no las 5 de la otra
    assert m["cost_savings"] == "Sin datos"  # antes "€100" (2 exitos x 50)
    assert m["savings_trend"] == "Sin datos"
    assert m["success_trend"] == "Sin datos"  # no hay periodo anterior con el que comparar
    assert "96" not in m["success_trend"]


def test_dashboard_metrics_no_invented_values(db):
    me, cme = _user(db)
    db.add(_act(me, cme.id))
    db.commit()
    body = TestClient(app).get("/api/v1/metrics/dashboard?days=30", headers=_h(me)).json()
    assert body["success"] is True
    assert body["total_interactions"] == 1
    assert body["cost_savings"] == "Sin datos"


def test_trends_compare_against_real_previous_period():
    class A:
        def __init__(self, status, secs):
            self.status = status
            self.created_at = datetime(2026, 1, 1)
            self.completed_at = self.created_at + timedelta(seconds=secs)

    cur = [A("completed", 2), A("completed", 2)]
    prev = [A("completed", 4), A("failed", 4)]
    t = _real_trends(cur, prev)
    assert t["interactions_trend"] == "estable"
    assert t["response_trend"] == "-50% vs periodo anterior"
    assert t["success_trend"] == "+50.0 pp vs periodo anterior"
    assert t["cost_savings"] == "Sin datos"


def test_metrics_require_auth():
    assert TestClient(app).get("/api/v1/metrics/summary").status_code in (401, 403)
