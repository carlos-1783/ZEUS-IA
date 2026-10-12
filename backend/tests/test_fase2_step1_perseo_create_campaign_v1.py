"""Fase 2 / Step 1 — PERSEO create_campaign: solo vista previa, NUNCA envia ni dice executed.

Antes `create_campaign` caia en la rama de envio del ejecutor (sin aprobacion, porque no esta en
CRITICAL_ACTIONS) y la rama de vista previa (inalcanzable) devolvia executed=True.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.user import User
from app.schemas.customer import CustomerCreate
import services.crm_office_service as crm_svc
from services.zeus_agent_executor_v1 import execute_agent_action


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
    c = Company(company_name=f"P {suf}", slug=f"p-{suf}")
    u = User(email=f"p_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


def test_create_campaign_is_preview_and_sends_nothing(db):
    u, c = _user(db)
    crm_svc.create_customer(db, u, CustomerCreate(name="Ana", email=f"ana_{uuid.uuid4().hex[:6]}@example.com"))
    db.commit()
    sent = AsyncMock(return_value={"success": True})
    with patch("services.zeus_orchestrator_handlers.email_service.send_email", sent), \
         patch("services.zeus_orchestrator_handlers.email_service.is_configured", return_value=True):
        r = asyncio.run(execute_agent_action(
            db, user=u, agent="PERSEO", action="create_campaign", payload={"discount_percent": 10}))
    assert r["success"] is True
    assert r["executed"] is False and r["status"] == "preview"
    assert r["data"]["customer_count"] == 1
    assert "no se ha enviado nada" in r["message"]
    assert "confirmar" not in r["message"]
    sent.assert_not_called()
    log = (db.query(AgentActivity)
           .filter(AgentActivity.company_id == c.id, AgentActivity.action_type == "agent_action_create_campaign")
           .order_by(AgentActivity.id.desc()).first())
    assert log is not None and log.status == "preview"


def test_create_campaign_counts_only_own_company(db):
    u, _ = _user(db)
    other, _ = _user(db)
    crm_svc.create_customer(db, other, CustomerCreate(name="Otro", email=f"o_{uuid.uuid4().hex[:6]}@example.com"))
    db.commit()
    r = asyncio.run(execute_agent_action(db, user=u, agent="PERSEO", action="create_campaign", payload={}))
    assert r["executed"] is False
    assert r["data"]["customer_count"] == 0
