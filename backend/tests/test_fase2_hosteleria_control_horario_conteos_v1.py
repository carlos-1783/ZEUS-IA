"""Fase 2 / vertical hosteleria — conteos del Control Horario por empresa (BD).

`/control-horario` y `/bootstrap` devolvian active_records_count/employees_count del
singleton en memoria del proceso, compartido entre empresas. Ahora salen de la BD
filtrados por la empresa del usuario: B no ve los fichajes activos ni la plantilla de A.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.user import User
from services.checkin_qr_token import issue_company_qr_token


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _seed(db, tag, n_emp):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"CH {tag} {suf}", slug=f"ch-{tag}-{suf}")
    u = User(email=f"ch_{tag}_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name=tag, is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    codes = []
    for i in range(n_emp):
        code = f"C{suf}{i}"
        codes.append(code)
        db.add(CompanyEmployee(company_id=c.id, employee_code=code, full_name=f"Emp {tag}{i}", hourly_rate=10.0))
    db.commit()
    db.refresh(u)
    return u, c.id, codes


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'email': u.email})}"}


def test_conteos_por_empresa(db):
    a, cid_a, codes_a = _seed(db, "a", 3)
    b, _, _ = _seed(db, "b", 1)
    client = TestClient(app)
    r = client.post("/api/v1/checkin", json={"company_id": cid_a, "employee_id": codes_a[0], "type": "entrada",
                                             "method": "qr", "qr_token": issue_company_qr_token(cid_a)},
                    headers=_h(a))
    assert r.status_code == 200, r.text

    info_a = client.get("/api/v1/control-horario", headers=_h(a)).json()
    info_b = client.get("/api/v1/control-horario", headers=_h(b)).json()
    assert info_a["active_records_count"] == 1 and info_a["employees_count"] == 3
    assert info_b["active_records_count"] == 0 and info_b["employees_count"] == 1

    boot_b = client.get("/api/v1/control-horario/bootstrap", headers=_h(b)).json()
    assert boot_b["info"]["active_records_count"] == 0
    assert all(str(e.get("id")) not in codes_a for e in boot_b["employees"])
