"""Fase 2 / Step 1 — RAFAEL desde el chat/voz: cierre de ventas TPV de ayer y facturas pendientes.

Datos reales de la BD, solo de la empresa del usuario, por el ejecutor (guard, modulo, registro).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.erp import Invoice, InvoiceStatus
from app.models.fiscal import TPVSale
from app.models.user import User
from app.schemas.zeus_action import ZeusAction
from services import jarvis_ops_actions as ops
from services.intent_parser import parse_intent
from services.local_day_v1 import day_bounds_utc, resolve_day


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
    c = Company(company_name=f"R {suf}", slug=f"r-{suf}")
    u = User(email=f"r_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


def _sale(db, u, cid, when, total, method="efectivo"):
    db.add(TPVSale(user_id=u.id, company_id=cid, ticket_id=f"T-{uuid.uuid4().hex[:10]}", document_type="ticket",
                   sale_date=when, payment_method=method, subtotal=round(total / 1.1, 2),
                   tax_amount=round(total - total / 1.1, 2), total=total))


def _chat(db, user, cid, action, payload=None, mods=None):
    act = ZeusAction(action_type=action, company_id=cid, user_id=user.id, payload=payload or {})
    with patch("services.module_gate.active_modules", return_value=mods or {"tpv": True}):
        return asyncio.run(ops.run_read_action(db, user, act))


def test_daily_close_yesterday_is_real_and_tenant_scoped(db):
    u, c = _user(db)
    ou, other = _user(db)
    start, end = day_bounds_utc(resolve_day("yesterday"))
    mid = start + (end - start) / 2
    _sale(db, u, c.id, mid, 22.0, "efectivo")
    _sale(db, u, c.id, mid + timedelta(hours=1), 11.0, "tarjeta")
    _sale(db, u, c.id, end + timedelta(minutes=5), 500.0)  # hoy: no cuenta
    _sale(db, u, c.id, start - timedelta(minutes=5), 700.0)  # anteayer: no cuenta
    _sale(db, ou, other.id, mid, 999.0)  # otra empresa: no se ve
    db.commit()
    r = _chat(db, u, c.id, "get_daily_close", {"day": "yesterday", "_zeus_context": {"x": 1}})
    assert r.success and r.executed
    assert r.metrics["tickets"] == 2 and r.metrics["total"] == 33.0
    assert r.metrics["by_payment_method"] == {"efectivo": {"count": 1, "total": 22.0},
                                              "tarjeta": {"count": 1, "total": 11.0}}
    assert r.metrics["cash_count_recorded"] is False
    assert "arqueo" in r.message and "33,00 €" in r.message
    log = (db.query(AgentActivity)
           .filter(AgentActivity.company_id == c.id, AgentActivity.action_type == "agent_action_get_daily_close")
           .order_by(AgentActivity.id.desc()).first())
    assert log is not None and log.status == "completed" and log.agent_name == "RAFAEL"


def test_daily_close_without_sales_says_so(db):
    u, c = _user(db)
    r = _chat(db, u, c.id, "get_daily_close")
    assert r.success and r.metrics["tickets"] == 0 and r.message.startswith("No hay ventas TPV")


def test_daily_close_invalid_or_future_day_fails_controlled(db):
    u, c = _user(db)
    for bad in ("mañana", "2999-01-01"):
        r = _chat(db, u, c.id, "get_daily_close", {"day": bad})
        assert r.success is False and r.executed is False and "Fecha no válida" in r.message


def test_daily_close_blocked_without_tpv_module(db):
    u, c = _user(db)
    r = _chat(db, u, c.id, "get_daily_close", mods={"tpv": False})
    assert r.success is False and r.executed is False and "TPV" in r.message


def test_pending_invoices_real_and_tenant_scoped(db):
    u, c = _user(db)
    ou, other = _user(db)
    past = datetime.utcnow() - timedelta(days=3)
    fut = datetime.utcnow() + timedelta(days=10)

    def inv(cid, status, total, paid=0.0, due=None):
        db.add(Invoice(invoice_number=f"F-{uuid.uuid4().hex[:10]}", company_id=cid, status=status,
                       total=total, amount_paid=paid, due_date=due))

    inv(c.id, InvoiceStatus.SENT, 100.0, due=fut)
    inv(c.id, InvoiceStatus.SENT, 50.0, due=past)  # vencida por fecha
    inv(c.id, InvoiceStatus.PARTIALLY_PAID, 80.0, paid=30.0)
    inv(c.id, InvoiceStatus.PAID, 40.0, paid=40.0)
    inv(c.id, InvoiceStatus.DRAFT, 10.0)
    inv(other.id, InvoiceStatus.OVERDUE, 9999.0)
    db.commit()
    r = _chat(db, u, c.id, "get_pending_invoices")
    assert r.success and r.executed
    m = r.metrics
    assert m["pending_count"] == 3 and m["pending_amount"] == 200.0
    assert m["overdue_count"] == 1 and m["overdue_amount"] == 50.0 and m["drafts_count"] == 1
    assert "200,00 €" in r.message and "vencida" in r.message


def test_pending_invoices_none(db):
    u, c = _user(db)
    r = _chat(db, u, c.id, "get_pending_invoices")
    assert r.success and r.message == "No tienes facturas pendientes de cobro."


def test_rafael_actions_rejected_with_other_agent(db):
    from services.zeus_agent_executor_v1 import execute_agent_action

    u, _ = _user(db)
    r = asyncio.run(execute_agent_action(db, user=u, agent="PERSEO", action="get_pending_invoices", payload={}))
    assert r["success"] is False and r["status"] == "agent_mismatch"


def test_intents():
    for m, day in (("cierre de ayer", "yesterday"), ("¿cómo fue el cierre de caja de ayer?", "yesterday"),
                   ("ventas de ayer", "yesterday"), ("cierre de caja de hoy", "today")):
        t = parse_intent(m)
        assert t.intent == "get_daily_close" and t.metadata.get("day") == day, (m, t.intent, t.metadata)
    for m in ("facturas pendientes", "¿qué facturas tengo pendientes de cobro?", "facturas vencidas"):
        assert parse_intent(m).intent == "get_pending_invoices", m
    assert parse_intent("ventas de hoy").intent == "tpv_sales_today"
    # «cierre» sin dia no se adivina: sigue siendo la consulta de caja/tesoreria de antes
    assert parse_intent("cierre de caja").intent != "get_daily_close"
