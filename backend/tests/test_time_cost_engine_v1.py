"""
E2E zeus_time_cost_engine_v1 — fichaje QR, sesión, coste parcial y cierre.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.employee_work_session import EmployeeWorkSession
from app.models.time_cost_checkin import TimeCostCheckin
from app.models.time_tracking import RecordStatus, TimeTrackingRecord
from app.models.user import User
from services.time_cost_engine_v1 import (
    get_cost_analytics,
    refresh_partial_costs,
    register_checkin,
)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_company_user_employee(db: Session, *, hourly_rate: float = 20.0):
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"tc_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Time Cost Tester",
        is_active=True,
    )
    company = Company(company_name=f"TC Co {suf}", slug=f"tc-{suf}")
    db.add_all([user, company])
    db.flush()

    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    emp = CompanyEmployee(
        company_id=company.id,
        full_name="Ana Worker",
        employee_code="EMP001",
        hourly_rate=hourly_rate,
        tpv_pin_hash=get_password_hash("1234"),
        is_active=True,
    )
    db.add(emp)
    db.commit()
    db.refresh(user)
    db.refresh(company)
    db.refresh(emp)
    return user, company, emp


def test_time_cost_engine_v1_e2e(db: Session):
    user, company, emp = _seed_company_user_employee(db, hourly_rate=30.0)
    employee_id = emp.employee_code

    entrada = register_checkin(
        db,
        user=user,
        company_id=company.id,
        employee_id=employee_id,
        checkin_type="entrada",
        method="qr",
        metadata={"qr_token": "tok-test-001"},
        client_ip="127.0.0.1",
        device_id="dev-e2e",
        user_agent="pytest",
    )
    assert entrada["success"] is True
    assert entrada["session_id"] is not None
    assert entrada["record_id"] is not None

    session_id = entrada["session_id"]
    record_id = entrada["record_id"]

    ws = db.query(EmployeeWorkSession).filter(EmployeeWorkSession.id == session_id).first()
    assert ws is not None
    assert ws.status == "active"

    record = db.query(TimeTrackingRecord).filter(TimeTrackingRecord.id == record_id).first()
    assert record is not None
    assert record.status == RecordStatus.ACTIVE

    checkins = db.query(TimeCostCheckin).filter(TimeCostCheckin.company_id == company.id).all()
    assert len(checkins) == 1
    assert checkins[0].type == "entrada"
    assert checkins[0].method == "qr"

    # Simular 10 minutos de jornada
    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    record.check_in_time = past
    ws.opened_at = past
    db.add(record)
    db.add(ws)
    db.commit()

    updated = refresh_partial_costs(db, company_id=company.id)
    assert updated >= 1

    db.refresh(ws)
    assert ws.partial_cost is not None
    assert ws.partial_cost > 0
    expected_hours = 10 / 60.0
    assert abs(float(ws.total_hours or 0) - expected_hours) < 0.05
    assert abs(float(ws.partial_cost or 0) - expected_hours * 30.0) < 0.5

    salida = register_checkin(
        db,
        user=user,
        company_id=company.id,
        employee_id=employee_id,
        checkin_type="salida",
        method="device",
        metadata={"device_id": "dev-e2e"},
    )
    assert salida["success"] is True
    assert salida["session_status"] == "closed"
    assert salida["cost_eur"] is not None
    assert abs(float(salida["cost_eur"]) - expected_hours * 30.0) < 0.5

    db.refresh(ws)
    assert ws.status == "closed"
    assert ws.total_cost is not None

    analytics = get_cost_analytics(db, user=user, company_id=company.id)
    assert analytics["total_hours_today"] >= expected_hours - 0.05
    assert analytics["total_cost_today"] >= expected_hours * 30.0 - 0.5

    all_checkins = (
        db.query(TimeCostCheckin)
        .filter(TimeCostCheckin.company_id == company.id)
        .order_by(TimeCostCheckin.id.asc())
        .all()
    )
    assert len(all_checkins) == 2
    assert all_checkins[-1].type == "salida"


def test_rejects_duplicate_open_session(db: Session):
    user, company, emp = _seed_company_user_employee(db)
    register_checkin(
        db,
        user=user,
        company_id=company.id,
        employee_id=emp.employee_code,
        checkin_type="entrada",
        method="qr",
        metadata={"qr_token": "tok-a"},
    )
    with pytest.raises(HTTPException) as exc:
        register_checkin(
            db,
            user=user,
            company_id=company.id,
            employee_id=emp.employee_code,
            checkin_type="entrada",
            method="qr",
            metadata={"qr_token": "tok-b"},
        )
    assert exc.value.status_code == 409


def test_rejects_invalid_method(db: Session):
    user, company, emp = _seed_company_user_employee(db)
    with pytest.raises(HTTPException) as exc:
        register_checkin(
            db,
            user=user,
            company_id=company.id,
            employee_id=emp.employee_code,
            checkin_type="entrada",
            method="invalid",
            metadata={},
        )
    assert exc.value.status_code == 422
