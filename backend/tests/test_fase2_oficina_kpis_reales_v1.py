"""Fase 2 / Oficina — KPIs del panel (Agentes, Tareas 24h, Eficiencia, Automatizaciones)
salen de datos reales de la cuenta, nunca de un numero fijo, y no mezclan empresas."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.user import User
from app.models.zeus_analytics import ZeusAutomationLog, ZeusEvent
from services.zeus_analytics_real_v1 import build_executive_analytics, list_automation_rows


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
    c = Company(company_name=f"K {suf}", slug=f"k-{suf}")
    u = User(email=f"kpi_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u


def _act(u, agent, status="completed"):
    return AgentActivity(agent_name=agent, action_type="x", action_description="t",
                         status=status, user_email=u.email)


def test_empty_account_shows_no_data_not_fixed_numbers(db):
    u = _user(db)
    ex = build_executive_analytics(db, u)
    assert ex["agents"] == 0          # antes: 6 fijo
    assert ex["automations"] == 0     # antes: 6 filas sembradas globales
    assert ex["tasks24h"] == 0
    assert ex["efficiency"] is None   # antes: 0 %
    assert list_automation_rows(db, u) == []


def test_kpis_count_only_own_tenant(db):
    me, other = _user(db), _user(db)
    db.add_all([
        _act(me, "PERSEO"), _act(me, "ZEUS"), _act(me, "PERSEO"),
        _act(other, "RAFAEL"), _act(other, "THALOS"), _act(other, "JUSTICIA"),
        ZeusEvent(type="t", agent="PERSEO", status="success", user_id=me.id),
        ZeusEvent(type="t", agent="PERSEO", status="failed", user_id=me.id),
        ZeusEvent(type="t", agent="RAFAEL", status="success", user_id=other.id),
        ZeusAutomationLog(automation_name="crm_payment_risk", status="success", user_id=me.id),
        ZeusAutomationLog(automation_name="crm_payment_risk", status="failed", user_id=me.id),
        ZeusAutomationLog(automation_name="teamflow_handoff", status="success", user_id=other.id),
        ZeusAutomationLog(automation_name="antigua", status="success", user_id=me.id,
                          executed_at=datetime.now(timezone.utc) - timedelta(days=60)),
    ])
    db.commit()

    ex = build_executive_analytics(db, me)
    assert ex["agents"] == 2  # PERSEO + ZEUS CORE, no los de la otra empresa
    assert ex["agents_total"] == 6
    assert ex["tasks24h"] == 2 and ex["success_events_24h"] == 1
    assert ex["efficiency"] == 50
    assert ex["automations"] == 1

    rows = list_automation_rows(db, me)
    assert [r["name"] for r in rows] == ["crm_payment_risk"]
    assert rows[0]["total_runs"] == 2
    assert "teamflow_handoff" not in [r["name"] for r in rows]


def test_endpoints_use_current_user_scope(db):
    me, other = _user(db), _user(db)
    db.add(ZeusAutomationLog(automation_name="solo_otra", status="success", user_id=other.id))
    db.commit()
    app.dependency_overrides[get_current_active_user] = lambda: me
    try:
        c = TestClient(app)
        r = c.get("/api/v1/analytics/automations")
        assert r.status_code == 200
        assert r.json()["automations"] == []
        r = c.get("/api/v1/analytics/executive")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True and body["automations"] == 0 and body["efficiency"] is None
    finally:
        app.dependency_overrides.clear()


def test_executive_failsafe_has_no_fixed_numbers(db, monkeypatch):
    from app.api.v1.endpoints import analytics as ep

    me = _user(db)

    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(ep, "build_executive_analytics", boom)
    app.dependency_overrides[get_current_active_user] = lambda: me
    try:
        body = TestClient(app).get("/api/v1/analytics/executive").json()
    finally:
        app.dependency_overrides.clear()
    assert body["success"] is False
    assert body["agents"] is None and body["efficiency"] is None and body["automations"] is None
