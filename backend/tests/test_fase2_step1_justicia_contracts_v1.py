"""Fase 2 / Step 1 — JUSTICIA «revisa mis contratos»: contratos reales de su empresa (legal_documents)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.legal_document import LegalDocument
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
    c = Company(company_name=f"J {suf}", slug=f"j-{suf}")
    u = User(email=f"j_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


def _chat(db, user, cid, mods=None):
    act = ZeusAction(action_type="review_contracts", company_id=cid, user_id=user.id)
    with patch("services.module_gate.active_modules", return_value=mods or {"agents": True}):
        return asyncio.run(ops.run_read_action(db, user, act))


def test_contracts_real_and_tenant_scoped(db):
    u, c = _user(db)
    ou, other = _user(db)
    now = datetime.now(timezone.utc)
    db.add_all([
        LegalDocument(user_id=u.id, company_id=c.id, doc_type="contract", content="a", status="draft"),
        LegalDocument(user_id=u.id, company_id=c.id, doc_type="contrato", content="b", status="draft"),
        LegalDocument(user_id=u.id, company_id=c.id, doc_type="contract", content="c", status="approved",
                      signed_at=now, signer_id=u.id),
        LegalDocument(user_id=u.id, company_id=c.id, doc_type="privacy_policy", content="d", status="draft"),
        LegalDocument(user_id=ou.id, company_id=other.id, doc_type="contract", content="x", status="draft"),
    ])
    db.commit()
    r = _chat(db, u, c.id)
    assert r.success and r.executed
    m = r.metrics
    assert m["total"] == 3 and m["by_status"] == {"draft": 2, "approved": 1}
    assert m["pending_review"] == 2 and m["signed"] == 1 and len(m["latest"]) == 3
    assert "2 borrador(es) sin firmar" in r.message
    log = (db.query(AgentActivity)
           .filter(AgentActivity.company_id == c.id, AgentActivity.action_type == "agent_action_review_contracts")
           .order_by(AgentActivity.id.desc()).first())
    assert log is not None and log.status == "completed" and log.agent_name == "JUSTICIA"


def test_no_contracts_says_so(db):
    u, c = _user(db)
    r = _chat(db, u, c.id)
    assert r.success and r.message == "No hay contratos guardados de tu empresa en JUSTICIA."


def test_blocked_without_agents_module(db):
    u, c = _user(db)
    r = _chat(db, u, c.id, mods={"agents": False})
    assert r.success is False and r.executed is False


def test_intents():
    for m in ("revisar contratos", "revisa mis contratos", "estado de los contratos", "contratos sin firmar"):
        assert parse_intent(m).intent == "review_contracts", m
    assert parse_intent("revisa el contrato RGPD").intent != "review_contracts"
    assert parse_intent("redacta un contrato de confidencialidad").intent != "review_contracts"
