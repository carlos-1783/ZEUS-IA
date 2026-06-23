"""E2E afrodita_real_execution_fix_v1 — empleados + fichaje QR con flags activos."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import os
from unittest.mock import patch

import pytest  # pyright: ignore[reportMissingImports]
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.time_cost_checkin import TimeCostCheckin
from app.models.user import User
from services.afrodita_control_layer_v1 import can_create_employee, can_execute_checkin
from services.afrodita_workspace_service_v1 import (
    create_company_employee,
    execute_qr_checkin,
    list_company_employees,
)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_user_company(db: Session):
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"af_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Afrodita Tester",
        is_active=True,
    )
    company = Company(company_name=f"AF Co {suf}", slug=f"af-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(user)
    db.refresh(company)
    return user, company


def _exec_flags():
    return patch.dict(
        os.environ,
        {
            "AFRODITA_EXECUTION_ENABLED": "true",
            "AFRODITA_READ_ONLY_MODE": "false",
        },
        clear=False,
    )


def test_can_create_and_checkin_flags():
    with _exec_flags():
        assert can_create_employee() is True
        assert can_execute_checkin() is True


def test_create_employee_blocked_without_flags(db: Session):
    user, _ = _seed_user_company(db)
    with pytest.raises(HTTPException) as exc:
        create_company_employee(
            db,
            user,
            full_name="Nuevo Empleado",
            employee_code="EMP-NEW",
        )
    assert exc.value.status_code == 403


def test_create_employee_e2e(db: Session):
    user, company = _seed_user_company(db)
    code = f"EMP-{uuid.uuid4().hex[:6]}"

    with _exec_flags():
        out = create_company_employee(
            db,
            user,
            full_name="Laura Real",
            employee_code=code,
            role_title="Cajera",
        )
        db.commit()

    assert out["employee"]["employee_code"] == code
    assert out["employee"]["company_id"] == company.id

    row = (
        db.query(CompanyEmployee)
        .filter(
            CompanyEmployee.company_id == company.id,
            CompanyEmployee.employee_code == code,
        )
        .first()
    )
    assert row is not None
    assert row.full_name == "Laura Real"

    listed = list_company_employees(db, user)
    codes = {e["employee_code"] for e in listed["employees"]}
    assert code in codes


def test_qr_checkin_persists_with_flags(db: Session):
    user, company = _seed_user_company(db)
    code = f"CHK-{uuid.uuid4().hex[:6]}"
    emp = CompanyEmployee(
        company_id=company.id,
        full_name="Fichador",
        employee_code=code,
        hourly_rate=15.0,
        is_active=True,
    )
    db.add(emp)
    db.commit()

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    qr = f"ZEUSCHECK|{code}|{ts}"

    with _exec_flags():
        result = execute_qr_checkin(db, user, qr)

    assert result.get("checkin_id")
    assert result["status"] == "executed"

    checkin = db.query(TimeCostCheckin).filter(TimeCostCheckin.id == result["checkin_id"]).first()
    assert checkin is not None
    assert checkin.company_id == company.id
    assert str(checkin.employee_id) == code


def test_qr_checkin_dry_run_without_flags(db: Session):
    user, company = _seed_user_company(db)
    code = f"RO-{uuid.uuid4().hex[:6]}"
    db.add(
        CompanyEmployee(
            company_id=company.id,
            full_name="Read Only",
            employee_code=code,
            is_active=True,
        )
    )
    db.commit()

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    qr = f"ZEUSCHECK|{code}|{ts}"

    result = execute_qr_checkin(db, user, qr)
    assert result.get("dry_run") is True
    assert result["status"] == "dry_run"
    assert "checkin_id" not in result
