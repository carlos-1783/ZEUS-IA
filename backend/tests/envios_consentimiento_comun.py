"""Fase 2 / auditoria final — utilidades comunes de los tests de envios con consentimiento.

Dobles SOLO en el test: el cliente Twilio (`whatsapp_service.client`) y el envio de email
(`email_service.send_email`). En produccion son los proveedores reales. Se ejercitan los
endpoints HTTP reales con JWT real (scopes), THALOS real, BD desechable y dos empresas.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.customer import Customer
from app.models.outbound_message import OutboundMessage
from app.models.reservation import Reservation
from app.models.user import User
from app.schemas.zeus_action import ZeusAction
from services import outbound_consent_v1 as oc
from services import zeus_orchestrator_handlers as handlers
from services.email_service import email_service
from services.whatsapp_service import WhatsAppService, whatsapp_service

BASE = "https://api.zeus.test"


# ------------------------------------------------------------------ fixtures


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
    return TestClient(app)


@pytest.fixture()
def public_base(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", BASE, raising=False)


class FakeTwilioMessages:
    def __init__(self) -> None:
        self.sent: List[Dict[str, Any]] = []

    def create(self, **params):
        self.sent.append(params)
        return SimpleNamespace(sid=f"SM{len(self.sent):04d}", status="queued")


@pytest.fixture()
def twilio(monkeypatch):
    msgs = FakeTwilioMessages()
    monkeypatch.setattr(whatsapp_service, "whatsapp_enabled", True)
    monkeypatch.setattr(whatsapp_service, "client", SimpleNamespace(messages=msgs))
    monkeypatch.setattr(whatsapp_service, "whatsapp_number", "whatsapp:+14155238886")
    return msgs


@pytest.fixture()
def mail(monkeypatch):
    calls: List[Dict[str, Any]] = []

    async def _send(to_email, subject, content, content_type="text/html", **kw):
        calls.append({"to": to_email, "subject": subject, "content": content})
        return {"success": True, "message_id": f"m{len(calls)}"}

    monkeypatch.setattr(email_service, "is_configured", lambda: True)
    monkeypatch.setattr(email_service, "send_email", _send)
    return calls


def _seed(db: Session, tag: str, *, superuser: bool = False):
    suf = uuid.uuid4().hex[:8]
    co = Company(company_name=f"Env {tag} {suf}", slug=f"env-{tag}-{suf}")
    db.add(co)
    db.flush()
    u = User(
        email=f"env_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"Env {tag}",
        is_active=True,
        is_superuser=superuser,
        company_name=f"Negocio {tag}",
        public_site_enabled=True,
        public_site_slug=f"slug-{tag}-{suf}",
    )
    db.add(u)
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=co.id, role="owner"))
    db.commit()
    db.refresh(u)
    db.refresh(co)
    return u, co


def _customer(db, co, *, consent=False, unsubscribed=False, email=None, phone=None, name="Cli"):
    suf = uuid.uuid4().hex[:6]
    c = Customer(
        name=f"{name} {suf}",
        email=email if email is not None else f"cli_{suf}@example.com",
        phone=phone,
        company_id=co.id,
        marketing_consent=consent,
        marketing_consent_at=datetime.now(timezone.utc) if consent else None,
        marketing_unsubscribed_at=datetime.now(timezone.utc) if unsubscribed else None,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _auth(u: User, scopes=("marketing:write",)) -> Dict[str, str]:
    tok = create_access_token({"sub": u.email, "email": u.email, "scopes": list(scopes)})
    return {"Authorization": f"Bearer {tok}"}


def _phone() -> str:
    return "+346" + str(uuid.uuid4().int)[:8]


def _outbound(db, **filters) -> List[OutboundMessage]:
    db.expire_all()
    q = db.query(OutboundMessage)
    for k, v in filters.items():
        q = q.filter(getattr(OutboundMessage, k) == v)
    return q.all()


def _campaign(db, user, co):
    action = ZeusAction(
        action_type="send_campaign", company_id=co.id, user_id=user.id,
        payload={"campaign_name": "Otono", "discount_percent": 10},
    )
    import asyncio

    return asyncio.run(handlers.execute_send_campaign(db, user, action))


