"""Fase 2 / Step 2 — handlers ZEUS sin fallback a superusuario ni ids/destinos del payload."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.user import User
from services.automation.handlers.zeus_automation_readiness import handle_automation_readiness_evaluate
from services.automation.handlers.zeus_orchestrator import _user_from_activity
from services.automation.handlers.zeus_payroll_draft import handle_payroll_draft_generate


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _user(db, company=None, superuser=False):
    suf = uuid.uuid4().hex[:8]
    if company is None:
        company = Company(company_name=f"Ten {suf}", slug=f"ten-{suf}")
        db.add(company)
        db.flush()
    u = User(email=f"ten_{suf}@example.com", hashed_password=get_password_hash("TestPass1"),
             is_active=True, is_superuser=superuser)
    db.add(u)
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=company.id, role="owner"))
    db.commit()
    return u, company


def _act(email, details, action="x"):
    return AgentActivity(id=0, agent_name="ZEUS", action_type=action, action_description="t",
                         details=details, user_email=email, company_id=None)


def test_orchestrator_no_superuser_fallback(db):
    _user(db, superuser=True)  # existe un superusuario: antes se usaba su tenant
    assert _user_from_activity(db, _act("", {})) is None
    assert _user_from_activity(db, _act("nadie@example.com", {})) is None


def test_readiness_ignores_payload_ids_and_phone(db):
    victim, _ = _user(db)
    me, _ = _user(db)
    _user(db, superuser=True)
    with patch("services.automation.handlers.zeus_automation_readiness.evaluate_and_persist") as ev:
        ev.return_value.status = "NOT_READY"
        ev.return_value.id = 1
        handle_automation_readiness_evaluate(_act(me.email, {"company_id": victim.id, "superuser_phone": "+34600000000"}))
    assert ev.call_args.args[1] == me.id

    with patch("services.automation.handlers.zeus_automation_readiness.evaluate_and_persist") as ev:
        out = handle_automation_readiness_evaluate(_act("", {"company_id": victim.id}))
    ev.assert_not_called()
    assert out["status"] == "failed"


def test_payroll_requires_employee_of_own_company_and_never_payload_recipient(db):
    me, comp = _user(db)
    colleague, _ = _user(db, company=comp)
    stranger, _ = _user(db)
    _user(db, superuser=True)
    gen = "services.automation.handlers.zeus_payroll_draft.generate_and_persist"
    send = "services.automation.handlers.zeus_payroll_draft.send_to_labor_advisor"

    with patch(gen) as g:
        out = handle_payroll_draft_generate(_act(me.email, {"gross_salary": 2000, "employee_id": stranger.id}))
    g.assert_not_called()
    assert out["status"] == "failed" and out["details_update"]["error"] == "employee_not_in_company"

    with patch(gen) as g:
        out = handle_payroll_draft_generate(_act("", {"gross_salary": 2000, "employee_id": colleague.id,
                                                     "company_id": stranger.id}))
    g.assert_not_called()
    assert out["details_update"]["error"] == "user_not_resolved"

    with patch(gen) as g, patch(send) as s:
        g.return_value = (type("R", (), {"id": 9, "gross_salary": 2000.0, "net_salary_estimated": 1600.0})(), None)
        handle_payroll_draft_generate(_act(me.email, {"gross_salary": 2000, "employee_id": colleague.id,
                                                     "company_id": stranger.id,
                                                     "email_gestor_laboral": "atacante@example.com"}))
    assert g.call_args.kwargs["company_id"] == me.id and g.call_args.kwargs["employee_id"] == colleague.id
    s.assert_not_called()  # el usuario no tiene gestor guardado: no se envia a nadie del payload
