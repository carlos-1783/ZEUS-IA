"""Fase 2 / vertical hosteleria — cierre de caja del TPV sobre la BD real.

Antes: TPVService.close_register calculaba expected_cash = initial_cash (ignoraba las
ventas) y no guardaba nada. Ahora el arqueo suma las ventas reales de la empresa
(tpv_sales) desde el ultimo cierre y persiste el cierre en tpv_cash_closures.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.fiscal import TPVSale
from app.models.tpv_cash_closure import TPVCashClosure
from app.models.user import User

P = "/api/v1/tpv/close-register"


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _seed(db, tag):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Bar {tag} {suf}", slug=f"bar-{tag}-{suf}")
    u = User(email=f"bar_{tag}_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name=tag, is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c.id


def _sale(db, user, cid, total, method, when=None):
    db.add(TPVSale(
        user_id=user.id, company_id=cid, ticket_id=f"T-{uuid.uuid4().hex[:12]}", document_type="ticket",
        sale_date=when or datetime.now(timezone.utc) - timedelta(minutes=5), payment_method=method,
        subtotal=Decimal(str(total)), tax_amount=Decimal("0"), total=Decimal(str(total)),
    ))
    db.commit()


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'email': u.email})}"}


def test_cierre_suma_ventas_reales_y_persiste(db):
    a, cid_a = _seed(db, "a")
    b, cid_b = _seed(db, "b")
    _sale(db, a, cid_a, 20, "efectivo")
    _sale(db, a, cid_a, 5.5, "efectivo")
    _sale(db, a, cid_a, 30, "tarjeta")
    _sale(db, a, cid_a, 7, "bizum")
    _sale(db, b, cid_b, 999, "efectivo")  # otra empresa: no puede entrar en el arqueo de A
    _sale(db, a, cid_a, 50, "efectivo", when=datetime.now(timezone.utc) - timedelta(days=3))  # otro dia

    client = TestClient(app)
    r = client.post(P, json={"terminal_id": "caja-1", "initial_cash": 100, "final_cash": 125.5}, headers=_h(a))
    assert r.status_code == 200, r.text
    cl = r.json()["closure"]
    assert cl["company_id"] == cid_a
    assert cl["sales_count"] == 4
    assert cl["cash_sales_total"] == 25.5
    assert cl["card_sales_total"] == 30.0
    assert cl["other_sales_total"] == 7.0
    assert cl["expected_cash"] == 125.5  # 100 inicial + 25.5 en efectivo (antes: 100)
    assert cl["difference"] == 0.0 and cl["status"] == "ok"

    db.expire_all()
    row = db.query(TPVCashClosure).filter(TPVCashClosure.id == cl["id"]).one()
    assert row.company_id == cid_a and row.user_id == a.id

    # Segundo cierre: solo ventas posteriores al primero; con descuadre real.
    _sale(db, a, cid_a, 10, "efectivo", when=datetime.now(timezone.utc))
    r2 = client.post(P, json={"terminal_id": "caja-1", "initial_cash": 0, "final_cash": 8}, headers=_h(a))
    assert r2.status_code == 200, r2.text
    cl2 = r2.json()["closure"]
    assert cl2["sales_count"] == 1 and cl2["cash_sales_total"] == 10.0
    assert cl2["expected_cash"] == 10.0 and cl2["difference"] == -2.0 and cl2["status"] == "discrepancy"
    assert cl2["period_start"] == cl["period_end"]


def test_otra_empresa_no_ve_los_cierres(db):
    a, cid_a = _seed(db, "a")
    b, cid_b = _seed(db, "b")
    _sale(db, a, cid_a, 12, "efectivo")
    client = TestClient(app)
    assert client.post(P, json={"terminal_id": "t1", "initial_cash": 0, "final_cash": 12},
                       headers=_h(a)).status_code == 200

    ra = client.get(P, headers=_h(a)).json()
    rb = client.get(P, headers=_h(b)).json()
    assert ra["company_id"] == cid_a and len(ra["closures"]) == 1
    assert rb["company_id"] == cid_b and rb["closures"] == []

    # B cierra su caja: no le cuentan las ventas de A.
    rb2 = client.post(P, json={"terminal_id": "t1", "initial_cash": 0, "final_cash": 0}, headers=_h(b))
    assert rb2.status_code == 200, rb2.text
    assert rb2.json()["closure"]["sales_count"] == 0
    assert rb2.json()["closure"]["expected_cash"] == 0.0


def test_errores_controlados(db):
    a, _ = _seed(db, "a")
    client = TestClient(app)
    assert client.post(P, json={"terminal_id": "t1", "initial_cash": 0, "final_cash": 0}).status_code == 401
    r = client.post(P, json={"terminal_id": "t1", "initial_cash": -1, "final_cash": 0}, headers=_h(a))
    assert r.status_code == 422
