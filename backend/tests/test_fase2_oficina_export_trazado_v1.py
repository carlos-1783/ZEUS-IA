"""Fase 2 / CRM oficina — exportar clientes/expedientes/cobros deja traza verificable
(log + crm_activity_log de la empresa) y solo exporta datos de la propia empresa."""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.crm_office import CrmActivityLog
from app.models.customer import Customer
from app.models.user import User


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
    c = Company(company_name=f"E {suf}", slug=f"e-{suf}")
    u = User(email=f"exp_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'email': u.email})}"}


def test_csv_export_scoped_and_traced(db, caplog):
    me, cme = _user(db)
    other, cother = _user(db)
    mine, theirs = f"Mio {uuid.uuid4().hex[:6]}", f"Ajeno {uuid.uuid4().hex[:6]}"
    db.add_all([
        Customer(name=mine, company_id=cme.id, owner_user_id=me.id, is_active=True),
        Customer(name=theirs, company_id=cother.id, owner_user_id=other.id, is_active=True),
    ])
    db.commit()
    with caplog.at_level(logging.INFO, logger="services.crm_export_audit"):
        r = TestClient(app).get("/api/v1/crm/export/clients", headers=_h(me))
    assert r.status_code == 200
    assert mine in r.text and theirs not in r.text
    assert any("crm_export entity=clients format=csv rows=1" in m for m in caplog.messages)
    db.expire_all()
    rows = db.query(CrmActivityLog).filter(CrmActivityLog.action == "data_export").all()
    assert [(x.company_id, x.user_id, x.payload["rows"]) for x in rows if x.company_id in (cme.id, cother.id)] \
        == [(cme.id, me.id, 1)]


def test_excel_export_traced(db):
    me, cme = _user(db)
    r = TestClient(app).get("/api/v1/office/export/cases/excel", headers=_h(me))
    assert r.status_code == 200
    db.expire_all()
    row = db.query(CrmActivityLog).filter(CrmActivityLog.company_id == cme.id,
                                          CrmActivityLog.action == "data_export").one()
    assert row.payload == {"entity": "cases", "format": "xlsx", "rows": 0}


def test_export_requires_auth():
    assert TestClient(app).get("/api/v1/crm/export/clients").status_code in (401, 403)
