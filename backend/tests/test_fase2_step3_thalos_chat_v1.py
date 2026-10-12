"""Fase 2 / Step 3 — THALOS ejecuta una consulta REAL desde el chat.

get_security_status: eventos THALOS solo de la empresa del usuario, por el ejecutor (guard,
control de modulos J4 "admin", registro de la ejecucion), y accesible por la intencion del chat.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from services.intent_parser import parse_intent
from services.zeus_agent_executor_v1 import execute_agent_action


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _user(db, superuser=False):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"S3 {suf}", slug=f"s3-{suf}")
    u = User(email=f"s3_{suf}@example.com", hashed_password=get_password_hash("TestPass1"),
             is_active=True, is_superuser=superuser)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


def _ev(db, company, action, severity="info", rule=None):
    db.add(ThalosSecurityEvent(event_type="request_guard", severity=severity, source="test",
                               company_id=company.id, action_taken=action, decision_rule=rule))
    db.commit()


def _run(db, user):
    return asyncio.run(execute_agent_action(db, user=user, agent="THALOS", action="get_security_status", payload={}))


def test_security_status_counts_only_own_company(db):
    admin, mine = _user(db, superuser=True)
    _, other = _user(db)
    _ev(db, mine, "allow")
    _ev(db, mine, "deny", "high", "control_characters")
    _ev(db, mine, "deny", "critical", "cross_tenant")
    for _ in range(4):
        _ev(db, other, "deny", "critical", "otra_empresa")

    out = _run(db, admin)
    assert out["success"] and out["executed"] and out["company_id"] == mine.id
    data = out["data"]
    assert data["events_total"] == 3 and data["denied_total"] == 2 and data["critical_total"] == 1
    assert {d["rule"] for d in data["recent_denials"]} == {"control_characters", "cross_tenant"}

    db.expire_all()
    log = (db.query(AgentActivity)
           .filter(AgentActivity.action_type == "agent_action_get_security_status",
                   AgentActivity.company_id == mine.id)
           .order_by(AgentActivity.id.desc()).first())
    assert log is not None and log.status == "completed"


def test_non_admin_is_blocked_by_module_like_thalos_agent(db):
    owner, _ = _user(db)
    out = _run(db, owner)
    assert out["success"] is False and out["status"] == "blocked_module" and out["module"] == "admin"


def test_chat_intent_routes_to_security_status():
    for msg in ("dame el estado de seguridad", "¿cuántos eventos de seguridad hubo?"):
        t = parse_intent(msg)
        assert t.intent == "get_security_status" and not t.needs_clarification
    assert parse_intent("estado legal").intent == "get_legal_status"
