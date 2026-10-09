"""J12b R9: analytics/TPV/turnos del orquestador filtran por la empresa activa de servidor
(nunca por email ni user_id como sustituto de empresa). Sin LLM ni red."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.employee_work_session import EmployeeWorkSession
from app.models.erp import TPVSale
from app.models.user import User
from app.schemas.zeus_action import ZeusAction
import services.zeus_orchestrator_handlers as h


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
    c = Company(company_name=f"R9 {suf}", slug=f"r9-{suf}")
    db.add(c)
    db.flush()
    return c


def _user(db, *companies):
    suf = uuid.uuid4().hex[:8]
    u = User(email=f"r9_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="R9", is_active=True)
    db.add(u)
    db.flush()
    for c in companies:
        db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u


def _act(db, company, email, n):
    for _ in range(n):
        db.add(AgentActivity(company_id=company.id, agent_name="ZEUS", action_type="x",
                             action_description="x", status="completed", user_email=email))
    db.commit()


def _sale(db, user, company, total):
    db.add(TPVSale(user_id=user.id, company_id=company.id, ticket_id=f"T-{uuid.uuid4().hex[:10]}",
                   document_type="ticket", sale_date=datetime.now(timezone.utc), payment_method="cash",
                   subtotal=total, tax_amount=0, recargo_amount=0, total=total))
    db.commit()


def _shift(db, user, company, code):
    db.add(EmployeeWorkSession(user_id=user.id, company_id=company.id, employee_code=code,
                               status="active", opened_at=datetime.now(timezone.utc)))
    db.commit()


def _act_(user, kind, company_id=None):
    return ZeusAction(action_type=kind, user_id=user.id, company_id=company_id, payload={"days": 30})


def test_usuario_en_dos_empresas_solo_ve_la_activa(db):
    a, b = _company(db), _company(db)
    u = _user(db, a, b)  # primaria = a
    _act(db, a, u.email, 2)
    _act(db, b, u.email, 5)  # mismo email, otra empresa: no debe contar
    _sale(db, u, a, 10)
    _sale(db, u, b, 1000)
    _shift(db, u, b, "EMP-B")
    r = h.execute_analytics_summary(db, u, _act_(u, "analytics_summary"))
    assert r.metrics["total"] == 2
    r = h.execute_tpv_sales_summary(db, u, _act_(u, "tpv_sales_summary"))
    assert r.metrics["sales_count"] == 1 and r.metrics["sales_total"] == 10
    r = h.execute_shift_status(db, u, _act_(u, "shift_status"))
    assert r.metrics["active"] is False  # el turno activo es de B, no de la empresa activa A
    # company_id explicito de una empresa del usuario si se respeta
    r = h.execute_tpv_sales_summary(db, u, _act_(u, "tpv_sales_summary", b.id))
    assert r.metrics["sales_total"] == 1000
    r = h.execute_shift_status(db, u, _act_(u, "shift_status", b.id))
    assert r.metrics["active"] is True


def test_usuario_de_b_no_ve_datos_de_a(db):
    a, b = _company(db), _company(db)
    ua, ub = _user(db, a), _user(db, b)
    _act(db, a, ua.email, 4)
    _sale(db, ua, a, 500)
    _shift(db, ua, a, "EMP-A")
    r = h.execute_analytics_summary(db, ub, _act_(ub, "analytics_summary"))
    assert r.metrics["total"] == 0
    r = h.execute_tpv_sales_summary(db, ub, _act_(ub, "tpv_sales_summary"))
    assert r.metrics["sales_count"] == 0
    assert h.execute_shift_status(db, ub, _act_(ub, "shift_status")).metrics["active"] is False
    # company_id ajeno forzado en la accion: se ignora, jamas se obtiene la analitica de A
    r = h.execute_tpv_sales_summary(db, ub, _act_(ub, "tpv_sales_summary", a.id))
    assert r.metrics["sales_count"] == 0 and r.metrics["sales_total"] == 0
    # (las propias consultas de ub quedan registradas en B: el total debe ser solo lo de B, no las 4 de A)
    propias_b = db.query(AgentActivity).filter(AgentActivity.company_id == b.id).count()
    r = h.execute_analytics_summary(db, ub, _act_(ub, "analytics_summary", a.id))
    assert r.metrics["total"] == propias_b and r.metrics["total"] < 4 + propias_b


def test_sin_empresa_error_controlado_aunque_haya_datos_por_email_o_user_id(db):
    a = _company(db)
    u = _user(db)  # sin empresa
    _act(db, a, u.email, 3)
    db.add(TPVSale(user_id=u.id, company_id=None, ticket_id=f"T-{uuid.uuid4().hex[:10]}",
                   document_type="ticket", sale_date=datetime.now(timezone.utc), payment_method="cash",
                   subtotal=9, tax_amount=0, recargo_amount=0, total=9))
    db.commit()
    for fn, kind in ((h.execute_analytics_summary, "analytics_summary"),
                     (h.execute_tpv_sales_summary, "tpv_sales_summary"),
                     (h.execute_shift_status, "shift_status")):
        r = fn(db, u, _act_(u, kind))
        assert r.success is False and r.executed is False and "empresa" in r.message
