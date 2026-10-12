"""Fase 2 / Step 1 — PERSEO «¿cómo van las ventas?» con datos reales de su empresa (TPV + facturas)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.erp import Invoice, InvoiceStatus
from app.models.fiscal import TPVSale, TPVSaleItem
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
    c = Company(company_name=f"S {suf}", slug=f"s-{suf}")
    u = User(email=f"s_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


def _sale(db, u, cid, days_ago, total, product="Café"):
    s = TPVSale(user_id=u.id, company_id=cid, ticket_id=f"T-{uuid.uuid4().hex[:10]}", document_type="ticket",
                sale_date=datetime.now(timezone.utc) - timedelta(days=days_ago), payment_method="tarjeta",
                subtotal=total, tax_amount=0, total=total)
    s.items.append(TPVSaleItem(product_id="p1", product_name=product, quantity=1, unit_price=total,
                               tax_rate_snapshot=0, tax_amount=0, base_amount=total))
    db.add(s)


def _chat(db, user, cid, payload=None):
    act = ZeusAction(action_type="get_sales_performance", company_id=cid, user_id=user.id, payload=payload or {})
    return asyncio.run(ops.run_read_action(db, user, act))


def test_sales_30_days_real_vs_previous_and_tenant_scoped(db):
    u, c = _user(db)
    ou, other = _user(db)
    _sale(db, u, c.id, 2, 60.0, "Menú")
    _sale(db, u, c.id, 10, 40.0, "Café")
    _sale(db, u, c.id, 40, 50.0)  # periodo anterior
    _sale(db, u, c.id, 70, 999.0)  # fuera de ambos periodos
    _sale(db, ou, other.id, 1, 5000.0)  # otra empresa
    now = datetime.utcnow()
    db.add_all([
        Invoice(invoice_number=f"F-{uuid.uuid4().hex[:8]}", company_id=c.id, status=InvoiceStatus.SENT,
                total=100.0, issue_date=now - timedelta(days=5)),
        Invoice(invoice_number=f"F-{uuid.uuid4().hex[:8]}", company_id=c.id, status=InvoiceStatus.DRAFT,
                total=777.0, issue_date=now - timedelta(days=5)),  # borrador: no es venta
        Invoice(invoice_number=f"F-{uuid.uuid4().hex[:8]}", company_id=other.id, status=InvoiceStatus.PAID,
                total=8888.0, issue_date=now - timedelta(days=5)),
    ])
    db.commit()
    r = _chat(db, u, c.id)
    assert r.success and r.executed
    m = r.metrics
    assert m["window_days"] == 30
    assert m["current"] == {"tpv_count": 2, "tpv_total": 100.0, "invoice_count": 1, "invoice_total": 100.0,
                            "total": 200.0}
    assert m["previous"]["total"] == 50.0 and m["change_pct"] == 300.0
    assert [p["name"] for p in m["top_products"]] == ["Menú", "Café"]
    assert "200,00 €" in r.message and "+300%" in r.message
    log = (db.query(AgentActivity)
           .filter(AgentActivity.company_id == c.id, AgentActivity.action_type == "agent_action_get_sales_performance")
           .order_by(AgentActivity.id.desc()).first())
    assert log is not None and log.status == "completed" and log.agent_name == "PERSEO"


def test_no_sales_says_so(db):
    u, c = _user(db)
    r = _chat(db, u, c.id)
    assert r.success and r.message.startswith("No hay ventas registradas")


def test_invalid_days_fails_controlled(db):
    u, c = _user(db)
    r = _chat(db, u, c.id, {"days": 5000})
    assert r.success is False and r.executed is False and "Periodo no válido" in r.message


def test_intents():
    for m, days in (("¿cómo van las ventas?", 30), ("como van mis ventas este mes", 30),
                    ("evolución de las ventas de los últimos 7 días", 7)):
        t = parse_intent(m)
        assert t.intent == "get_sales_performance" and t.metadata.get("days") == days, (m, t.intent)
    assert parse_intent("¿cómo van las ventas de hoy?").intent == "tpv_sales_today"
    assert parse_intent("como van las ventas de ayer").intent == "get_daily_close"
