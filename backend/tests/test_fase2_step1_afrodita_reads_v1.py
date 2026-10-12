"""Fase 2 / Step 1 — AFRODITA desde el chat/voz: fichajes de hoy (sin biometria), agenda de hoy y
pedidos (sin modelo: bloqueo honesto). Solo datos de la empresa del usuario."""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.crm_lead import CrmLead
from app.models.reservation import Reservation
from app.models.time_tracking import RecordStatus, TimeTrackingRecord
from app.models.user import User
from app.schemas.zeus_action import ZeusAction
from services import jarvis_ops_actions as ops
from services.intent_parser import parse_intent
from services.local_day_v1 import day_bounds_utc, today_local


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
    c = Company(company_name=f"A {suf}", slug=f"a-{suf}")
    u = User(email=f"a_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


def _chat(db, user, cid, action, mods=None):
    act = ZeusAction(action_type=action, company_id=cid, user_id=user.id)
    with patch("services.module_gate.active_modules", return_value=mods or {"control_horario": True}):
        return asyncio.run(ops.run_read_action(db, user, act))


def _log(db, cid, action):
    return (db.query(AgentActivity)
            .filter(AgentActivity.company_id == cid, AgentActivity.action_type == f"agent_action_{action}")
            .order_by(AgentActivity.id.desc()).first())


def test_attendance_today_real_and_tenant_scoped(db):
    u, c = _user(db)
    ou, other = _user(db)
    start, _ = day_bounds_utc(today_local())
    t0 = start + timedelta(hours=7)
    db.add_all([
        TimeTrackingRecord(employee_id="E1", user_id=u.id, company_id=c.id, check_in_time=t0,
                           status=RecordStatus.ACTIVE, is_late_check_in=True),
        TimeTrackingRecord(employee_id="E2", user_id=u.id, company_id=c.id, check_in_time=t0,
                           check_out_time=t0 + timedelta(hours=4), hours_worked=4.0,
                           status=RecordStatus.COMPLETED),
        TimeTrackingRecord(employee_id="E3", user_id=u.id, company_id=c.id,
                           check_in_time=start - timedelta(days=3), status=RecordStatus.COMPLETED,
                           check_out_time=start - timedelta(days=3) + timedelta(hours=8)),
        TimeTrackingRecord(employee_id="X", user_id=ou.id, company_id=other.id, check_in_time=t0,
                           status=RecordStatus.ACTIVE),
    ])
    db.commit()
    r = _chat(db, u, c.id, "get_attendance_status")
    assert r.success and r.executed
    m = r.metrics
    assert (m["checkins_today"], m["employees_today"], m["currently_in"], m["late_today"]) == (2, 2, 1, 1)
    assert m["hours_closed_today"] == 4.0 and m["biometric_data_used"] is False
    assert "dentro: 1" in r.message and "entrada tarde" in r.message
    log = _log(db, c.id, "get_attendance_status")
    assert log is not None and log.status == "completed" and log.agent_name == "AFRODITA"


def test_attendance_blocked_without_control_horario(db):
    u, c = _user(db)
    r = _chat(db, u, c.id, "get_attendance_status", mods={"control_horario": False})
    assert r.success is False and r.executed is False and "Control horario" in r.message


def test_agenda_today_real_and_tenant_scoped(db):
    u, c = _user(db)
    ou, other = _user(db)
    today = today_local()
    start, _ = day_bounds_utc(today)
    db.add_all([
        Reservation(user_id=u.id, company_id=c.id, guest_name="Lucía", guest_phone="600000000",
                    reservation_date=today, reservation_time="21:00", num_guests=4, status="confirmed"),
        Reservation(user_id=u.id, company_id=c.id, guest_name="Anulada", guest_phone="600000001",
                    reservation_date=today, reservation_time="20:00", num_guests=2, status="cancelled"),
        Reservation(user_id=u.id, company_id=c.id, guest_name="Mañana", guest_phone="600000002",
                    reservation_date=today + timedelta(days=1), reservation_time="14:00", num_guests=2),
        Reservation(user_id=ou.id, company_id=other.id, guest_name="Ajena", guest_phone="600000003",
                    reservation_date=today, reservation_time="13:00", num_guests=8),
        CrmLead(company_id=c.id, name="Acme", status="open", meeting_at=start + timedelta(hours=9)),
        CrmLead(company_id=other.id, name="Otra", status="open", meeting_at=start + timedelta(hours=9)),
    ])
    db.commit()
    r = _chat(db, u, c.id, "get_today_agenda")
    assert r.success and r.executed
    m = r.metrics
    assert (m["reservations"], m["guests"], m["meetings"]) == (1, 4, 1)
    assert {i["name"] for i in m["items"]} == {"Lucía", "Acme"}
    assert "Lucía (4 pax)" in r.message and "reunión con Acme" in r.message
    assert _log(db, c.id, "get_today_agenda").status == "completed"


def test_agenda_empty_says_so(db):
    u, c = _user(db)
    r = _chat(db, u, c.id, "get_today_agenda")
    assert r.success and r.message == "Hoy no tienes reservas ni reuniones en la agenda de tu empresa."


def test_orders_is_honest_block_and_logged(db):
    u, c = _user(db)
    r = _chat(db, u, c.id, "get_weekly_orders")
    assert r.success is False and r.executed is False
    assert "no tiene un registro de pedidos" in r.message
    log = _log(db, c.id, "get_weekly_orders")
    assert log is not None and log.status == "failed"


def test_intents():
    for m in ("¿quién ha fichado hoy?", "estado de los fichajes", "fichajes de hoy", "¿quiénes están trabajando?"):
        assert parse_intent(m).intent == "get_attendance_status", m
    assert parse_intent("estado de mis fichajes").intent == "shift_status"
    for m in ("agenda de hoy", "¿qué hay en mi agenda?", "reservas de hoy"):
        assert parse_intent(m).intent == "get_today_agenda", m
    assert parse_intent("agenda de mañana").intent != "get_today_agenda"
    assert parse_intent("agenda una reunión con Juan").intent != "get_today_agenda"
    assert parse_intent("pedidos de esta semana").intent == "get_weekly_orders"
