"""
ZEUS time & cost engine v1 — fichajes reales, validación y coste laboral.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.company import UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.employee_work_session import EmployeeWorkSession
from app.models.time_cost_checkin import TimeCostCheckin
from app.models.time_tracking import RecordStatus, TimeTrackingRecord
from app.models.user import User
from services import smart_time_control_service as sm
from services.zeus_office_mode import require_company_id

logger = logging.getLogger(__name__)

VALID_METHODS = frozenset({"qr", "pin", "geo", "device", "nfc"})
VALID_TYPES = frozenset({"entrada", "salida", "pausa_inicio", "pausa_fin"})
MAX_SESSION_HOURS = 16
ALERT_EXCESS_HOURS = 12
V1_TO_RECORD_METHOD = {"geo": "location", "device": "remote", "pin": "code", "qr": "qr", "nfc": "qr"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _resolve_employee(
    db: Session,
    *,
    company_id: int,
    employee_id: str,
) -> CompanyEmployee:
    emp = (
        db.query(CompanyEmployee)
        .filter(
            CompanyEmployee.company_id == company_id,
            CompanyEmployee.employee_code == str(employee_id),
            CompanyEmployee.is_active.is_(True),
        )
        .first()
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado no encontrado para esta empresa.")
    return emp


def _assert_user_company_access(db: Session, user: User, company_id: int) -> None:
    require_company_id(company_id, context="fichaje")
    if getattr(user, "is_superuser", False):
        return
    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id, UserCompany.company_id == company_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=403, detail="No tienes acceso a la empresa indicada.")


def _validate_method_payload(method: str, metadata: Dict[str, Any]) -> None:
    m = method.lower()
    if m == "qr" and not str(metadata.get("qr_token") or "").strip():
        raise HTTPException(status_code=422, detail="qr_token requerido para método qr.")
    if m == "pin" and not str(metadata.get("pin") or "").strip():
        raise HTTPException(status_code=422, detail="pin requerido para método pin.")
    if m == "geo":
        if metadata.get("lat") is None or metadata.get("lng") is None:
            raise HTTPException(status_code=422, detail="lat y lng requeridos para método geo.")
    if m == "device" and not str(metadata.get("device_id") or "").strip():
        raise HTTPException(status_code=422, detail="device_id requerido para método device.")
    if m == "nfc" and not str(metadata.get("nfc_token") or metadata.get("qr_token") or "").strip():
        raise HTTPException(status_code=422, detail="nfc_token requerido para método nfc.")


def _verify_pin(emp: CompanyEmployee, pin: str) -> None:
    from app.core.security import verify_password

    pin_hash = getattr(emp, "tpv_pin_hash", None)
    if not pin_hash:
        raise HTTPException(status_code=422, detail="Empleado sin PIN configurado.")
    if not verify_password(pin, pin_hash):
        raise HTTPException(status_code=403, detail="PIN incorrecto.")


def _active_record(
    db: Session,
    *,
    user_id: int,
    employee_id: str,
) -> Optional[TimeTrackingRecord]:
    return (
        db.query(TimeTrackingRecord)
        .filter(
            TimeTrackingRecord.user_id == user_id,
            TimeTrackingRecord.employee_id == str(employee_id),
            TimeTrackingRecord.status == RecordStatus.ACTIVE,
        )
        .order_by(TimeTrackingRecord.id.desc())
        .first()
    )


def _active_work_session(
    db: Session,
    *,
    company_id: int,
    employee_code: str,
) -> Optional[EmployeeWorkSession]:
    return (
        db.query(EmployeeWorkSession)
        .filter(
            EmployeeWorkSession.company_id == company_id,
            EmployeeWorkSession.employee_code == str(employee_code),
            EmployeeWorkSession.status == "active",
        )
        .order_by(EmployeeWorkSession.id.desc())
        .first()
    )


def _session_duration_hours(start: datetime, end: datetime, pause_minutes: float = 0.0) -> float:
    if not start or not end:
        return 0.0
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    delta = (end - start).total_seconds() / 3600.0
    pause_h = float(pause_minutes or 0) / 60.0
    return max(0.0, round(delta - pause_h, 4))


def _compute_cost(hours: float, hourly_rate: float) -> float:
    return round(max(0.0, hours) * max(0.0, float(hourly_rate or 0)), 2)


def _update_session_cost(
    db: Session,
    *,
    session: EmployeeWorkSession,
    record: TimeTrackingRecord,
    emp: CompanyEmployee,
    final: bool = False,
) -> Tuple[float, float]:
    end = record.check_out_time or _now()
    pause_min = float(session.pause_minutes or record.break_duration or 0) * (
        60.0 if (session.pause_minutes or 0) < 24 else 1.0
    )
    if record.break_duration and (session.pause_minutes or 0) < 1:
        pause_min = float(record.break_duration) * 60.0
    hours = _session_duration_hours(session.opened_at, end, pause_min)
    rate = float(getattr(emp, "hourly_rate", None) or 0)
    cost = _compute_cost(hours, rate)
    session.total_hours = hours
    if final:
        session.total_cost = cost
        session.partial_cost = cost
    else:
        session.partial_cost = cost
    record.hours_worked = hours
    db.add(session)
    db.add(record)
    return hours, cost


def _reject_if_session_too_long(record: TimeTrackingRecord) -> None:
    if not record or not record.check_in_time:
        return
    start = _ensure_utc(record.check_in_time)
    if not start:
        return
    hours = (_now() - start).total_seconds() / 3600.0
    if hours > MAX_SESSION_HOURS:
        raise HTTPException(
            status_code=422,
            detail=f"Sesión abierta supera {MAX_SESSION_HOURS}h; contacta con administración.",
        )


def register_checkin(
    db: Session,
    *,
    user: User,
    company_id: int,
    employee_id: str,
    checkin_type: str,
    method: str,
    metadata: Optional[Dict[str, Any]] = None,
    client_ip: Optional[str] = None,
    device_id: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa fichaje v1 y devuelve estado de sesión + coste."""
    cid = require_company_id(company_id, context="checkin")
    _assert_user_company_access(db, user, cid)

    ctype = str(checkin_type or "").strip().lower()
    m = str(method or "").strip().lower()
    if ctype not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"type inválido. Válidos: {sorted(VALID_TYPES)}")
    if m not in VALID_METHODS:
        raise HTTPException(status_code=422, detail=f"method inválido. Válidos: {sorted(VALID_METHODS)}")

    meta = dict(metadata or {})
    _validate_method_payload(m, meta)
    emp = _resolve_employee(db, company_id=cid, employee_id=employee_id)
    if m == "pin":
        _verify_pin(emp, str(meta.get("pin") or ""))

    now = _now()
    record = _active_record(db, user_id=user.id, employee_id=employee_id)
    work_session = _active_work_session(db, company_id=cid, employee_code=employee_id)

    if ctype == "entrada":
        if record:
            _reject_if_session_too_long(record)
            raise HTTPException(status_code=409, detail="Ya existe una sesión abierta para este empleado.")
        method_map = V1_TO_RECORD_METHOD
        check_method = method_map.get(m, m)
        record = TimeTrackingRecord(
            employee_id=str(employee_id),
            user_id=user.id,
            check_in_time=now,
            check_in_method=check_method,
            check_in_latitude=meta.get("lat"),
            check_in_longitude=meta.get("lng"),
            check_in_location=meta.get("location"),
            status=RecordStatus.ACTIVE,
        )
        db.add(record)
        db.flush()

        if not work_session:
            work_session = EmployeeWorkSession(
                user_id=user.id,
                company_id=cid,
                employee_code=str(employee_id),
                time_tracking_record_id=record.id,
                status="active",
                opened_at=now,
                last_activity_at=now,
                pause_minutes=0.0,
            )
            db.add(work_session)
            db.flush()

        sm.append_event(
            db,
            user_id=user.id,
            employee_id=str(employee_id),
            record_id=record.id,
            event_type="check-in",
            occurred_at=now,
            location=meta.get("location"),
            latitude=meta.get("lat"),
            longitude=meta.get("lng"),
            device=device_id or user_agent,
            extra_payload={"engine": "v1", "method": m},
        )

    elif ctype == "salida":
        if not record:
            raise HTTPException(status_code=422, detail="No hay sesión abierta para cerrar.")
        _reject_if_session_too_long(record)
        record.check_out_time = now
        record.check_out_method = V1_TO_RECORD_METHOD.get(m, m)
        record.status = RecordStatus.COMPLETED
        hours, cost = 0.0, 0.0
        if work_session:
            hours, cost = _update_session_cost(db, session=work_session, record=record, emp=emp, final=True)
            work_session.status = "closed"
            work_session.closed_at = now
            work_session.close_reason = "checkin_salida"
            work_session.last_activity_at = now
        else:
            hours = _session_duration_hours(record.check_in_time, now)
            cost = _compute_cost(hours, float(getattr(emp, "hourly_rate", None) or 0))
            record.hours_worked = hours

        sm.append_event(
            db,
            user_id=user.id,
            employee_id=str(employee_id),
            record_id=record.id,
            event_type="check-out",
            occurred_at=now,
            location=meta.get("location"),
            latitude=meta.get("lat"),
            longitude=meta.get("lng"),
            device=device_id or user_agent,
            extra_payload={"engine": "v1", "hours": hours, "cost": cost},
        )

    elif ctype == "pausa_inicio":
        if not record:
            raise HTTPException(status_code=422, detail="No hay sesión activa para pausar.")
        try:
            sm.validate_break_transition(db, user.id, record, "break-start")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        sm.append_event(
            db,
            user_id=user.id,
            employee_id=str(employee_id),
            record_id=record.id,
            event_type="break-start",
            occurred_at=now,
            location=meta.get("location"),
            latitude=meta.get("lat"),
            longitude=meta.get("lng"),
            device=device_id or user_agent,
            extra_payload={"engine": "v1"},
        )

    elif ctype == "pausa_fin":
        if not record:
            raise HTTPException(status_code=422, detail="No hay sesión activa para reanudar.")
        try:
            sm.validate_break_transition(db, user.id, record, "break-end")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        _, brk, _ = sm.compute_hours_with_break_events(
            db,
            user_id=user.id,
            record=record,
            check_out_time=now,
            fallback_break_hours=float(record.break_duration or 0),
        )
        brk = float(brk or 0)
        if work_session:
            work_session.pause_minutes = brk * 60.0
        record.break_duration = brk
        sm.append_event(
            db,
            user_id=user.id,
            employee_id=str(employee_id),
            record_id=record.id,
            event_type="break-end",
            occurred_at=now,
            location=meta.get("location"),
            latitude=meta.get("lat"),
            longitude=meta.get("lng"),
            device=device_id or user_agent,
            extra_payload={"engine": "v1"},
        )

    checkin_row = TimeCostCheckin(
        company_id=cid,
        employee_id=str(employee_id),
        company_employee_id=emp.id,
        user_id=user.id,
        type=ctype,
        method=m,
        timestamp=now,
        time_tracking_record_id=record.id if record else None,
        work_session_id=work_session.id if work_session else None,
        metadata_json=json.dumps(meta, ensure_ascii=False),
        client_ip=client_ip,
        device_id=device_id or meta.get("device_id"),
        user_agent=(user_agent or "")[:512] or None,
    )
    db.add(checkin_row)
    db.flush()

    partial_cost = None
    total_hours = None
    if record and record.status == RecordStatus.ACTIVE and work_session:
        _, partial_cost = _update_session_cost(
            db, session=work_session, record=record, emp=emp, final=False
        )
        total_hours = work_session.total_hours
    elif record and record.status == RecordStatus.COMPLETED:
        total_hours = record.hours_worked
        partial_cost = work_session.total_cost if work_session else _compute_cost(
            float(record.hours_worked or 0),
            float(getattr(emp, "hourly_rate", None) or 0),
        )

    db.commit()
    db.refresh(checkin_row)

    from services.event_bus import (
        emit_alert_triggered,
        emit_cost_updated,
        emit_employee_checked_in,
        emit_session_closed,
        emit_session_started,
    )

    if ctype == "entrada":
        emit_employee_checked_in(
            user_id=user.id,
            user_email=user.email,
            company_id=cid,
            employee_id=str(employee_id),
            checkin_id=checkin_row.id,
            db=db,
        )
        if work_session:
            emit_session_started(
                user_id=user.id,
                user_email=user.email,
                company_id=cid,
                employee_id=str(employee_id),
                session_id=work_session.id,
                db=db,
            )
    if ctype == "salida" and work_session:
        emit_session_closed(
            user_id=user.id,
            user_email=user.email,
            company_id=cid,
            employee_id=str(employee_id),
            session_id=work_session.id,
            total_hours=total_hours,
            total_cost=partial_cost,
            db=db,
        )
    if partial_cost is not None:
        emit_cost_updated(
            user_id=user.id,
            user_email=user.email,
            company_id=cid,
            employee_id=str(employee_id),
            cost=partial_cost,
            hours=total_hours,
            db=db,
        )

    if record and record.check_in_time and not record.check_out_time:
        cin = _ensure_utc(record.check_in_time)
        open_h = (_now() - cin).total_seconds() / 3600.0 if cin else 0.0
        if open_h > ALERT_EXCESS_HOURS:
            emit_alert_triggered(
                user_id=user.id,
                user_email=user.email,
                company_id=cid,
                employee_id=str(employee_id),
                alert_type="exceso_horas",
                detail=f"Sesión > {ALERT_EXCESS_HOURS}h",
                db=db,
            )
        if open_h > MAX_SESSION_HOURS:
            emit_alert_triggered(
                user_id=user.id,
                user_email=user.email,
                company_id=cid,
                employee_id=str(employee_id),
                alert_type="sesion_abierta",
                detail=f"Sesión abierta > {MAX_SESSION_HOURS}h",
                db=db,
            )

    return {
        "success": True,
        "checkin_id": checkin_row.id,
        "type": ctype,
        "method": m,
        "employee_id": str(employee_id),
        "company_id": cid,
        "record_id": record.id if record else None,
        "session_id": work_session.id if work_session else None,
        "session_status": work_session.status if work_session else None,
        "hours": total_hours,
        "cost_eur": partial_cost,
        "hourly_rate": float(getattr(emp, "hourly_rate", None) or 0),
        "timestamp": now.isoformat(),
    }


def get_active_sessions(
    db: Session,
    *,
    user: User,
    company_id: int,
) -> List[Dict[str, Any]]:
    cid = require_company_id(company_id, context="sesiones activas")
    _assert_user_company_access(db, user, cid)
    rows = (
        db.query(EmployeeWorkSession)
        .filter(
            EmployeeWorkSession.company_id == cid,
            EmployeeWorkSession.status == "active",
        )
        .order_by(EmployeeWorkSession.opened_at.desc())
        .all()
    )
    out: List[Dict[str, Any]] = []
    for ws in rows:
        emp = (
            db.query(CompanyEmployee)
            .filter(
                CompanyEmployee.company_id == cid,
                CompanyEmployee.employee_code == ws.employee_code,
            )
            .first()
        )
        rate = float(getattr(emp, "hourly_rate", None) or 0) if emp else 0.0
        record = None
        if ws.time_tracking_record_id:
            record = (
                db.query(TimeTrackingRecord)
                .filter(TimeTrackingRecord.id == ws.time_tracking_record_id)
                .first()
            )
        if record and record.status == RecordStatus.ACTIVE and emp:
            _update_session_cost(db, session=ws, record=record, emp=emp, final=False)
        out.append(
            {
                "session_id": ws.id,
                "employee_id": ws.employee_code,
                "employee_name": getattr(emp, "full_name", None) or ws.employee_code,
                "started_at": ws.opened_at.isoformat() if ws.opened_at else None,
                "hours": float(ws.total_hours or 0),
                "real_time_cost_eur": float(ws.partial_cost or 0),
                "hourly_rate": rate,
                "status": ws.status,
            }
        )
    if out:
        db.commit()
    return out


def get_cost_analytics(
    db: Session,
    *,
    user: User,
    company_id: int,
) -> Dict[str, Any]:
    cid = require_company_id(company_id, context="analytics fichajes")
    _assert_user_company_access(db, user, cid)

    start, end = _today_range()
    sessions = (
        db.query(EmployeeWorkSession)
        .filter(
            EmployeeWorkSession.company_id == cid,
            EmployeeWorkSession.opened_at >= start,
            EmployeeWorkSession.opened_at < end,
        )
        .all()
    )
    active = (
        db.query(EmployeeWorkSession)
        .filter(
            EmployeeWorkSession.company_id == cid,
            EmployeeWorkSession.status == "active",
        )
        .count()
    )

    total_hours = sum(float(s.total_hours or 0) for s in sessions)
    total_cost = sum(float(s.total_cost or s.partial_cost or 0) for s in sessions)
    employee_ids = {s.employee_code for s in sessions}
    avg_cost = round(total_cost / len(employee_ids), 2) if employee_ids else 0.0

    return {
        "company_id": cid,
        "total_hours_today": round(total_hours, 2),
        "total_cost_today": round(total_cost, 2),
        "average_cost_per_employee": avg_cost,
        "active_employees": active,
        "sessions_today": len(sessions),
    }


def _today_range() -> Tuple[datetime, datetime]:
    now = _now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def refresh_partial_costs(db: Session, *, company_id: int) -> int:
    """Actualiza coste parcial de sesiones activas (regla cada 5 min)."""
    updated = 0
    sessions = (
        db.query(EmployeeWorkSession)
        .filter(
            EmployeeWorkSession.company_id == company_id,
            EmployeeWorkSession.status == "active",
        )
        .all()
    )
    for ws in sessions:
        record = None
        if ws.time_tracking_record_id:
            record = db.query(TimeTrackingRecord).filter(TimeTrackingRecord.id == ws.time_tracking_record_id).first()
        if not record or record.status != RecordStatus.ACTIVE:
            continue
        emp = (
            db.query(CompanyEmployee)
            .filter(
                CompanyEmployee.company_id == company_id,
                CompanyEmployee.employee_code == ws.employee_code,
            )
            .first()
        )
        if not emp:
            continue
        _update_session_cost(db, session=ws, record=record, emp=emp, final=False)
        updated += 1
    if updated:
        db.commit()
    return updated
