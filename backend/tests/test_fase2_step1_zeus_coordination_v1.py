"""Fase 2 / Step 1 — ZEUS informe de coordinacion real desde el chat (solo su empresa)."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval
from app.schemas.zeus_action import ZeusAction
from services import jarvis_ops_actions as ops
from services.intent_parser import parse_intent


@pytest.fixture()
def db():
    from app.db.base import _migrate_zeus_approvals_chat_columns, _migrate_zeus_approvals_execution_columns

    Base.metadata.create_all(bind=engine)
    _migrate_zeus_approvals_execution_columns()
    _migrate_zeus_approvals_chat_columns()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _user(db):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Z {suf}", slug=f"z-{suf}")
    u = User(email=f"z_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


def _act(cid, agent, action, status):
    return AgentActivity(agent_name=agent, action_type=action, action_description=action, status=status,
                         company_id=cid)


def _chat(db, user, cid):
    act = ZeusAction(action_type="get_coordination_report", company_id=cid, user_id=user.id)
    return asyncio.run(ops.run_read_action(db, user, act))


def test_coordination_report_real_and_tenant_scoped(db):
    u, c = _user(db)
    ou, other = _user(db)
    db.add_all([
        _act(c.id, "RAFAEL", "x", "completed"),
        _act(c.id, "RAFAEL", "y", "completed"),
        _act(c.id, "PERSEO", "send", "failed"),
        _act(other.id, "THALOS", "ajena", "failed"),
        ZeusPendingApproval(company_id=c.id, user_id=u.id, agent_name="PERSEO", action_type="send_campaign",
                            payload_json="{}", status="pending"),
    ])
    db.commit()
    r = _chat(db, u, c.id)
    assert r.success and r.executed
    m = r.metrics
    assert m["activities_by_agent"] == {"PERSEO": {"failed": 1}, "RAFAEL": {"completed": 2}}
    assert [p["action_type"] for p in m["problems"]] == ["send"]
    assert m["pending_approvals"] == {"PERSEO": 1}
    assert "3 actividades" in r.message and "PERSEO 1" in r.message
    log = (db.query(AgentActivity)
           .filter(AgentActivity.company_id == c.id,
                   AgentActivity.action_type == "agent_action_get_coordination_report")
           .order_by(AgentActivity.id.desc()).first())
    assert log is not None and log.status == "completed" and log.agent_name == "ZEUS"


def test_empty_company_says_so(db):
    u, c = _user(db)
    r = _chat(db, u, c.id)
    assert r.success and r.message.startswith("No hay actividad de los agentes")


def test_intents():
    for m in ("¿cómo van mis agentes?", "informe de coordinación", "resumen de los agentes",
              "¿qué han hecho los agentes?"):
        assert parse_intent(m).intent == "get_coordination_report", m
    assert parse_intent("dame la actividad del sistema").intent == "analytics_summary"
