"""Facturas: labels de los ENUM de BD = las de produccion; contrato de API = codigos en ingles.

Causa del 500 de /invoices en produccion: app/models/erp.py emitia labels en ingles ('draft',
'invoice'...) y los tipos ENUM `invoicestatus`/`invoicetype` de PostgreSQL de produccion tienen
otras (enum_range confirmado en Railway). Estos tests fijan:
  1. los .value EXACTOS de produccion (lo que viaja a la BD con values_callable);
  2. que la API, el chat (rafael_daily_reads_v1 / jarvis_ops_actions) y la ventana siguen usando los
     codigos de app.schemas.erp (draft/sent/paid/...; invoice/...), traducidos por NOMBRE de miembro;
  3. que los filtros de GET /invoices aceptan esos codigos y rechazan con 422 lo demas (antes, el
     string pasaba tal cual a la consulta: en Postgres, 500).
La prueba contra PostgreSQL real (tipos con labels de produccion) va aparte: aqui es SQLite.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.erp import Invoice, InvoiceStatus, InvoiceType
from app.models.user import User
from app.schemas import erp as schemas
from services import rafael_daily_reads_v1 as reads
from services.jarvis_ops_actions import _format_read
from services.local_day_v1 import day_bounds_utc, today_local

API = settings.API_V1_STR

PROD_STATUS = {"DRAFT": "borrador", "SENT": "enviado", "PAID": "pagado",
               "PARTIALLY_PAID": "partially_paid", "VOID": "anulado", "OVERDUE": "vencido"}
PROD_TYPE = {"INVOICE": "factura", "CREDIT_NOTE": "credit_note", "PROFORMA": "proforma",
             "ESTIMATE": "estimación"}
API_STATUS = {"DRAFT": "draft", "SENT": "sent", "PAID": "paid", "PARTIALLY_PAID": "partially_paid",
              "VOID": "void", "OVERDUE": "overdue"}
API_TYPE = {"INVOICE": "invoice", "CREDIT_NOTE": "credit_note", "PROFORMA": "proforma", "ESTIMATE": "estimate"}


def test_model_values_are_exact_production_labels():
    assert {m.name: m.value for m in InvoiceStatus} == PROD_STATUS
    assert {m.name: m.value for m in InvoiceType} == PROD_TYPE
    # Lo que SQLAlchemy manda a la BD es el .value (values_callable), en el orden del tipo de produccion.
    assert Invoice.__table__.c.status.type.enums == list(PROD_STATUS.values())
    assert Invoice.__table__.c.invoice_type.type.enums == list(PROD_TYPE.values())
    assert "estimación" in Invoice.__table__.c.invoice_type.type.enums  # con tilde, tal cual


def test_api_contract_codes_unchanged_and_translation_by_name():
    assert {m.name: m.value for m in schemas.InvoiceStatus} == API_STATUS
    assert {m.name: m.value for m in schemas.InvoiceType} == API_TYPE
    for m in InvoiceStatus:
        assert schemas.invoice_status_code(m) == API_STATUS[m.name]
        assert schemas.InvoiceStatus(API_STATUS[m.name]).name == m.name
    for m in InvoiceType:
        assert schemas.invoice_type_code(m) == API_TYPE[m.name]
    assert schemas.invoice_status_code(None) is None
    assert schemas.invoice_status_code("paid") == "paid"
    with pytest.raises(ValueError):
        schemas.invoice_status_code("pagado")  # label de BD no es un codigo de API
    with pytest.raises(ValueError):
        schemas.invoice_type_code("bogus")


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _company(db):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Enum {suf}", slug=f"enum-{suf}")
    u = User(email=f"enum_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    return u, c


def _inv(db, cid, status, itype=InvoiceType.INVOICE, total=100.0, paid=0.0, due_days=10, day=None):
    # Emision DENTRO del dia LOCAL `day` (inicio del dia en UTC naive + margen), como
    # _today_start_naive_utc() de test_rafael_lecturas_chat_v1: no depende de la hora a la que corra
    # el test (con utcnow() - 5 min fallaba entre las 00:00 y las 00:05 de Madrid).
    now = datetime.utcnow()
    day_start = day_bounds_utc(day or today_local())[0].replace(tzinfo=None)
    issue = day_start + timedelta(minutes=1) if due_days >= 0 else day_start + timedelta(days=due_days - 30)
    inv = Invoice(invoice_number=f"E-{uuid.uuid4().hex[:10]}", company_id=cid, invoice_type=itype, status=status,
                  issue_date=issue, due_date=now + timedelta(days=due_days), subtotal=round(total / 1.21, 2),
                  tax_amount=round(total - total / 1.21, 2), discount_amount=0.0, total=total, amount_paid=paid,
                  amount_due=max(total - paid, 0.0))
    db.add(inv)
    db.flush()
    return inv


def test_orm_stores_production_label_and_reads_back_every_member(db):
    _, c = _company(db)
    ids = [(_inv(db, c.id, st).id, st) for st in InvoiceStatus]
    ids += [(_inv(db, c.id, InvoiceStatus.SENT, itype=t).id, t) for t in InvoiceType]
    db.commit()
    db.expire_all()
    for iid, member in ids:
        col = "status" if isinstance(member, InvoiceStatus) else "invoice_type"
        raw = db.execute(text(f"SELECT {col} FROM invoices WHERE id = :i"), {"i": iid}).scalar()
        assert raw == member.value  # en la BD queda la label de produccion
        inv = db.get(Invoice, iid)
        assert getattr(inv, col) is member
        # Respuesta de la API: codigo en ingles (no 'pagado'), sin ValidationError.
        out = schemas.InvoiceInDB.model_validate(inv).model_dump(mode="json")
        assert out["status"] == API_STATUS[inv.status.name]
        assert out["invoice_type"] == API_TYPE[inv.invoice_type.name]


def test_rafael_reads_and_chat_text_with_production_labels(db):
    _, c = _company(db)
    _, other = _company(db)
    today = today_local()  # una sola vez: mismo dia local para fechar y para leer
    _inv(db, c.id, InvoiceStatus.SENT, total=200.0, day=today)
    _inv(db, c.id, InvoiceStatus.PARTIALLY_PAID, total=100.0, paid=40.0, day=today)
    _inv(db, c.id, InvoiceStatus.OVERDUE, total=50.0, due_days=-2, day=today)
    _inv(db, c.id, InvoiceStatus.PAID, total=30.0, paid=30.0, day=today)
    _inv(db, c.id, InvoiceStatus.DRAFT, total=70.0, day=today)
    _inv(db, c.id, InvoiceStatus.VOID, total=80.0, day=today)
    _inv(db, c.id, InvoiceStatus.SENT, itype=InvoiceType.ESTIMATE, total=999.0, day=today)  # no es factura
    _inv(db, other.id, InvoiceStatus.SENT, total=5000.0, day=today)  # otra empresa
    db.commit()

    pend = reads.pending_invoices_summary(db, c.id)
    assert pend["pending_count"] == 3 and pend["pending_amount"] == 310.0
    assert pend["overdue_count"] == 1 and pend["drafts_count"] == 1
    assert {i["status"] for i in pend["top"]} == {"sent", "partially_paid", "overdue"}

    day = reads.invoices_day_summary(db, c.id, today)
    # hoy: SENT, PARTIALLY_PAID, PAID, DRAFT, VOID (la OVERDUE se emitio hace >30 dias)
    assert day["by_status"] == {"sent": 1, "partially_paid": 1, "paid": 1, "draft": 1, "void": 1}
    assert day["count"] == 3 and day["amount_total"] == 330.0
    assert day["drafts_count"] == 1 and day["void_count"] == 1
    assert {i["status"] for i in day["invoices"]} <= set(API_STATUS.values())
    txt = _format_read("get_invoices_today", {"data": day})
    assert "1 borrador(es) sin emitir" in txt and "1 anulada(s)" in txt

    last = reads.last_invoice_summary(db, c.id)
    assert last["found"] and last["invoices_count"] == 6
    assert last["invoice"]["status"] in API_STATUS.values()

    other_pend = reads.pending_invoices_summary(db, other.id)
    assert other_pend["pending_count"] == 1 and other_pend["pending_amount"] == 5000.0


@pytest.mark.usefixtures("no_external_messaging")
def test_list_invoices_filters_take_api_codes_and_reject_db_labels():
    from app.main import app

    with TestClient(app) as client:
        suf = uuid.uuid4().hex[:10]
        payload = {"email": f"invenum_{suf}@example.com", "password": "TestPass1", "full_name": "Titular Enum",
                   "phone": "612345678", "company_name": f"Empresa Enum {suf}", "business_type": "restaurant"}
        r = client.post(f"{API}/auth/register", json=payload)
        if r.status_code != 201:
            pytest.skip(f"Registro no disponible: {r.status_code}")
        login = client.post(f"{API}/auth/login", data={"username": payload["email"], "password": payload["password"]})
        assert login.status_code == 200, login.text
        h = {"Authorization": f"Bearer {login.json()['access_token']}"}
        cust = client.post(f"{API}/customers", headers=h,
                           json={"name": "Cliente Enum", "email": f"ce_{suf}@example.com"})
        assert cust.status_code == 201, cust.text
        created = {}
        for st in ("draft", "paid"):
            rr = client.post(f"{API}/invoices/", headers=h, json={
                "customer_id": cust.json()["data"]["id"], "invoice_type": "invoice", "status": st,
                "issue_date": "2026-01-10",
                "items": [{"description": "Servicio", "quantity": 1, "unit_price": 10.0, "tax_rate": 21.0}]})
            assert rr.status_code == 201, rr.text
            assert rr.json()["data"]["status"] == st and rr.json()["data"]["invoice_type"] == "invoice"
            created[st] = rr.json()["data"]["id"]

        db = SessionLocal()
        try:
            raw = db.execute(text("SELECT status, invoice_type FROM invoices WHERE id = :i"),
                             {"i": created["paid"]}).one()
            assert tuple(raw) == ("pagado", "factura")
        finally:
            db.close()

        r = client.get(f"{API}/invoices/?status=paid", headers=h)
        assert r.status_code == 200, r.text
        assert [d["id"] for d in r.json()["data"]] == [created["paid"]]
        assert r.json()["data"][0]["status"] == "paid"
        r = client.get(f"{API}/invoices/?status=draft&invoice_type=invoice", headers=h)
        assert r.status_code == 200 and [d["id"] for d in r.json()["data"]] == [created["draft"]]
        r = client.get(f"{API}/invoices/?invoice_type=estimate", headers=h)
        assert r.status_code == 200 and r.json()["total"] == 0
        for bad in ("status=pagado", "status=bogus", "invoice_type=factura"):
            r = client.get(f"{API}/invoices/?{bad}", headers=h)
            assert r.status_code == 422, (bad, r.status_code, r.text)
