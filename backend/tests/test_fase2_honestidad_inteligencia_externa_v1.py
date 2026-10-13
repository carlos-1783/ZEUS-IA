"""Fase 2 / honestidad final #14 — /zeus-core/intelligence/research sin fuente externa:
501 external_source_not_configured y sin sobrescribir los insights del lead."""

from __future__ import annotations

import uuid

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.crm_lead import CrmLead
from app.models.user import User


def _path() -> str:
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path.endswith("/intelligence/research"):
            return r.path
    raise AssertionError("ruta no montada")


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_501_y_no_toca_el_lead(db):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Ext {suf}", slug=f"ext-{suf}")
    u = User(email=f"ext_{suf}@example.test", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    lead = CrmLead(company_id=c.id, name="Lead", external_insights_json='{"previo": "dato real"}')
    db.add(lead)
    db.commit()
    db.refresh(u)
    db.refresh(lead)
    app.dependency_overrides[get_current_active_user] = lambda: u
    try:
        r = TestClient(app).post(_path(), params={"query": "Acme SL", "lead_id": lead.id})
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
    assert r.status_code == 501, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "external_source_not_configured" and detail["persisted"] is False
    db.expire_all()
    assert db.query(CrmLead).filter(CrmLead.id == lead.id).one().external_insights_json == '{"previo": "dato real"}'
