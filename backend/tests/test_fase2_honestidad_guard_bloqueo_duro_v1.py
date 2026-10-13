"""Fase 2 / honestidad final #18 — zeus_core_guard: bloqueos duros con independencia de flags.

Con ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED y ZEUS_CORE_GUARD_ENFORCE en su valor por defecto (False):
- accion destructiva sobre usuario protegido/superusuario -> bloqueada (antes solo se registraba);
- pagos/facturas/cashflow/crm sin company_id -> bloqueado (antes ni se evaluaba).
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.cashflow_ledger import CashflowLedgerEntry
from app.models.company import Company, UserCompany
from app.models.user import User
from services.financial_integrity_v1 import assert_financial_record_valid
from services.user_service_v1 import secure_deactivate
from services.zeus_agent_executor_v1 import execute_agent_action
from services.zeus_core_guard_v1 import (
    ZeusGuardViolation,
    apply_guard,
    guard_enforce,
    validate_critical_action,
)


@pytest.fixture()
def db(monkeypatch):
    monkeypatch.setattr(settings, "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", False)
    monkeypatch.setattr(settings, "ZEUS_CORE_GUARD_ENFORCE", False)
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _user(db, *, superuser=False):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"G {suf}", slug=f"g-{suf}")
    u = User(email=f"g_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             is_active=True, is_superuser=superuser)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


def test_flags_por_defecto_apagados(db):
    assert guard_enforce() is False


def test_superusuario_destructivo_bloqueado_siempre(db):
    su, _ = _user(db, superuser=True)
    gr = validate_critical_action("users", "delete_user", target_user=su, db=db)
    assert gr.allowed is False and gr.enforced is True and gr.reason == "protected_user_or_superuser"
    with pytest.raises(ZeusGuardViolation):
        apply_guard(gr, db=db)
    out = secure_deactivate(db, su, reason="test")
    assert out["executed"] is False and out["status"] == "blocked_by_guard"
    db.refresh(su)
    assert su.is_active is True


def test_usuario_normal_no_se_bloquea(db):
    u, _ = _user(db)
    gr = validate_critical_action("users", "deactivate_user", target_user=u, db=db)
    assert gr.allowed is True


@pytest.mark.parametrize("domain", ["payments", "invoices", "cashflow", "crm"])
def test_sin_empresa_bloqueado_siempre(db, domain):
    gr = validate_critical_action(domain, "create", company_id=None, db=db)
    assert gr.allowed is False and gr.enforced is True and gr.reason == "company_id_required"
    with pytest.raises(ZeusGuardViolation):
        apply_guard(gr, db=db)


def test_con_empresa_permitido(db):
    _, c = _user(db)
    assert validate_critical_action("payments", "create", company_id=c.id, db=db).allowed is True
    fin = assert_financial_record_valid(db, company_id=c.id, amount=10.0)
    assert fin["valid"] is True and fin["blocked"] is False


def test_ledger_sin_empresa_bloqueado(db):
    fin = assert_financial_record_valid(db, company_id=None, amount=10.0)
    assert fin["blocked"] is True and fin["valid"] is False


def test_event_bus_cashflow_sin_empresa_no_escribe(db):
    from services.event_bus import emit_cashflow_updated

    before = db.query(CashflowLedgerEntry).count()
    emit_cashflow_updated(user_id=None, user_email=None, company_id=None, amount=50.0, source="TEST", db=db)
    db.expire_all()
    assert db.query(CashflowLedgerEntry).count() == before


def test_executor_superusuario_accion_destructiva_bloqueada(db):
    su, _ = _user(db, superuser=True)
    out = asyncio.run(execute_agent_action(db, user=su, agent="ZEUS", action="block_user", payload={}))
    assert out["success"] is False and out["executed"] is False
    assert out["execution_mode"] == "blocked"
