"""Fase 2 / Step 3 — PERSEO: seguimiento de leads REAL desde el chat (solo su empresa)."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import patch

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.crm_lead import CrmLead
from app.models.user import User
from app.schemas.zeus_action import ZeusAction
from services import jarvis_ops_actions as ops
from services.intent_parser import parse_intent


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
    c = Company(company_name=f"L {suf}", slug=f"l-{suf}")
    u = User(email=f"l_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


def _chat(db, user, cid):
    act = ZeusAction(action_type="track_leads", company_id=cid, user_id=user.id)
    # El modulo CRM lo decide la configuracion real de la empresa; aqui se fija activo.
    with patch("services.module_gate.active_modules", return_value={"crm": True}):
        return asyncio.run(ops.run_read_action(db, user, act))


def test_leads_from_chat_are_real_and_tenant_scoped(db):
    u, c = _user(db)
    _, other = _user(db)
    db.add_all([
        CrmLead(company_id=c.id, name="A", status="open", customer_priority="high"),
        CrmLead(company_id=c.id, name="B", status="open"),
        CrmLead(company_id=c.id, name="C", status="converted"),
        CrmLead(company_id=other.id, name="X", status="open", customer_priority="high"),
    ])
    db.commit()
    r = _chat(db, u, c.id)
    assert r.success and r.executed
    assert r.metrics == {"open_leads": 2, "high_priority": 1, "with_meeting": 0}
    assert "2" in r.message and "prioridad alta" in r.message


def test_no_leads_says_so(db):
    u, c = _user(db)
    r = _chat(db, u, c.id)
    assert r.success and r.message == "No tienes leads abiertos en el CRM de tu empresa."


def test_crm_module_off_blocks(db):
    u, c = _user(db)
    act = ZeusAction(action_type="track_leads", company_id=c.id, user_id=u.id)
    with patch("services.module_gate.active_modules", return_value={"crm": False}):
        r = asyncio.run(ops.run_read_action(db, u, act))
    assert r.success is False and r.executed is False


def test_intent():
    for m in ("¿cuántos leads tengo?", "leads abiertos", "estado de mis leads"):
        assert parse_intent(m).intent == "track_leads"
