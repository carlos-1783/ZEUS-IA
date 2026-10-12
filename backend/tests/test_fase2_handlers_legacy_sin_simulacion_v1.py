"""Fase 2 / Step 2 — los handlers legacy ya no devuelven entregables fijos.

- ZEUS coordination: informe con datos reales de la BD, solo de la empresa de la actividad.
- PERSEO/RAFAEL/AFRODITA task_assigned: bloqueadas con motivo explicito (sin entregable).
- THALOS task_assigned: delega en el ciclo real de monitorizacion.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval
from services.automation.handlers import resolve_handler


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _company(db, superuser=False):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Leg {suf}", slug=f"leg-{suf}")
    u = User(email=f"leg_{suf}@example.com", hashed_password=get_password_hash("TestPass1"),
             is_active=True, is_superuser=superuser)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    return u, c


def _act(db, u, c, agent, action, status="pending"):
    a = AgentActivity(agent_name=agent, action_type=action, action_description=f"{agent} {action}",
                      details={}, status=status, user_email=u.email, company_id=c.id)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def test_zeus_report_uses_real_data_of_own_company_only(db):
    u, c = _company(db)
    other_u, other_c = _company(db)
    _act(db, u, c, "PERSEO", "campaign_created", status="completed")
    _act(db, u, c, "RAFAEL", "invoice_sent", status="failed")
    _act(db, other_u, other_c, "RAFAEL", "invoice_sent", status="failed")  # otra empresa
    db.add(ZeusPendingApproval(company_id=c.id, user_id=u.id, agent_name="AFRODITA",
                               action_type="create_ops_route", payload_json="{}", status="pending"))
    db.commit()
    task = _act(db, u, c, "ZEUS CORE", "coordination")

    with patch("services.automation.utils.store_output", return_value=None):
        out = resolve_handler("ZEUS CORE", "coordination")(task)

    rep = out["details_update"]["automation"]["report"]
    assert out["status"] == "completed" and out["details_update"]["real_execution"] is True
    assert rep["company_id"] == c.id and rep["source"] == "database"
    assert rep["activities_total"] == 2
    assert rep["activities_by_agent"] == {"PERSEO": {"completed": 1}, "RAFAEL": {"failed": 1}}
    assert [p["status"] for p in rep["problems"]] == ["failed"]
    assert rep["pending_approvals"] == {"AFRODITA": 1}
    assert "Plan maestro activo" not in str(out)
    assert "R2 no configurado" in out["notes"]


@pytest.mark.parametrize("agent", ["PERSEO", "RAFAEL", "AFRODITA"])
def test_generic_tasks_without_logic_are_blocked_explicitly(db, agent):
    u, c = _company(db)
    out = resolve_handler(agent, "task_assigned")(_act(db, u, c, agent, "task_assigned"))
    assert out["status"] == "blocked_missing_handler"
    assert out["details_update"]["real_execution"] is False
    assert "no tiene logica real" in out["notes"]
    assert "deliverables" not in str(out)


def test_thalos_task_assigned_runs_real_monitor(db):
    u, c = _company(db, superuser=True)
    task = _act(db, u, c, "THALOS", "task_assigned")
    with patch("services.automation.handlers.thalos_v1.handle_thalos_v1_monitor",
               return_value={"status": "completed", "notes": "real"}) as mon:
        out = resolve_handler("THALOS", "task_assigned")(task)
    mon.assert_called_once()
    assert out == {"status": "completed", "notes": "real"}
