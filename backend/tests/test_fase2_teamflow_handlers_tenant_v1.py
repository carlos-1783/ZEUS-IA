"""Fase 2 / Step 2 — handlers TeamFlow: factura persistida de verdad y con empresa.

- invoice_sent pasaba title=/content= (no son columnas): TypeError siempre, nunca persistia.
- invoice_sent y ads_campaign_builder creaban DocumentApproval sin company_id.
- sin usuario resoluble se actuaba con el primer superusuario.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.document_approval import DocumentApproval
from app.models.user import User
from services import teamflow_real_handlers_v1 as h


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
    c = Company(company_name=f"TF {suf}", slug=f"tf-{suf}")
    u = User(email=f"tf_{suf}@example.com", hashed_password=get_password_hash("TestPass1"),
             is_active=True, is_superuser=superuser)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    return u.id, u.email, c.id


def _act(email, action, details, company_id=None):
    return AgentActivity(id=4242, agent_name="X", action_type=action, action_description="t",
                         details=details, user_email=email, company_id=company_id)


def test_invoice_sent_really_persists_with_company(db):
    uid, email, cid = _user(db)
    _, _, other_cid = _user(db)
    with patch("services.zeus_event_bus_v1.emit_event"):
        out = h.handle_invoice_sent(_act(email, "invoice_sent", {"invoice_number": "F-77"}, company_id=other_cid))
    assert out["status"] == "completed", out
    doc_id = out["details_update"]["real_handler"]["document_approval_id"]
    db.expire_all()
    doc = db.query(DocumentApproval).filter(DocumentApproval.id == doc_id).one()
    assert doc.user_id == uid and doc.company_id == cid  # la empresa ajena de la actividad se ignora
    assert doc.document_payload["title"] == "F-77"


def test_ads_builder_draft_has_company(db):
    uid, email, cid = _user(db)

    def no_api(*a, **k):
        raise HTTPException(status_code=503, detail="meta_not_configured")

    with patch("services.perseo_ads_engine_v2.create_ad_campaign", no_api):
        out = h.handle_ads_campaign_builder(_act(email, "ads_campaign_builder", {"campaign_name": "C1"}))
    assert out["status"] == "failed" and "NO se ha publicado" in out["notes"]
    db.expire_all()
    doc = (db.query(DocumentApproval).filter(DocumentApproval.user_id == uid)
           .order_by(DocumentApproval.id.desc()).first())
    assert doc.company_id == cid and doc.document_type == "marketing_campaign"


def test_no_superuser_fallback(db):
    _user(db, superuser=True)
    s = SessionLocal()
    try:
        assert h._user_from_activity(s, _act("", "invoice_sent", {})) is None
    finally:
        s.close()
    out = h.handle_invoice_sent(_act("", "invoice_sent", {"invoice_number": "F-1"}))
    assert out["status"] == "failed"
