"""
Jornada laboral = sesión empleado + fichaje (TimeTrackingRecord).
Login → clock-in automático; logout → clock-out; TPV actualiza actividad y puede cerrar por idle.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company_employee import CompanyEmployee
from app.models.employee_work_session import EmployeeWorkSession
from app.models.time_tracking import CheckInMethod, RecordStatus, TimeTrackingRecord
from app.models.user import User
from services import smart_time_control_service as sm
from services.control_horario_singleton import control_horario_service
from services.event_bus import emit_time_control_event
from services.tpv_operator_context import primary_company_id, session_company_employee

logger = logging.getLogger(__name__)


def _user_role(user: User) -> str:
    return (getattr(user, "role", None) or "owner").strip().lower()


def _idle_delta() -> timedelta:
    mins = max(5, int(getattr(settings, "WORK_SESSION_IDLE_MINUTES", 30)))
    return timedelta(minutes=mins)


def _close_tracking_row_at(
    db: Session,
    *,
    user: User,
    employee_code: str,
    active: TimeTrackingRecord,
    checkout_time: datetime,
    close_reason: str,
    device: Optional[str] = None,
) -> None:
    """Persiste salida en BD + evento smart (horas en servidor)."""
    net, brk, extra = sm.compute_hours_with_break_events(
        db,
        user_id=user.id,
        record=active,
        check_out_time=checkout_time,
        fallback_break_hours=0.0,
    )
    active.check_out_time = checkout_time
    active.check_out_method = CheckInMethod.REMOTE
    active.check_out_location = "auto_session_close"
    active.hours_worked = net
    active.break_duration = brk
    active.extra_hours = extra
    active.status = RecordStatus.COMPLETED
    prev_notes = active.notes or ""
    active.notes = prev_notes + f"\n[{close_reason}]"
    db.add(active)
    db.flush()
    sm.append_event(
        db,
        user_id=user.id,
        employee_id=str(employee_code),
        record_id=active.id,
        event_type="check-out",
        occurred_at=checkout_time,
        location="auto_session_close",
        latitude=None,
        longitude=None,
        device=(device or "")[:512] or None,
        extra_payload={
            "hours_worked": float(net or 0),
            "extra_hours": float(extra or 0),
            "close_reason": close_reason,
        },
    )


def _close_active_sessions_and_records(
    db: Session,
    user: User,
    employee_code: str,
    checkout_time: datetime,
    reason: str,
) -> None:
    """Cierra sesiones de trabajo y registros ACTIVE previos (login duplicado / superseded)."""
    sm.sync_runtime_active_records(db, user, control_horario_service)
    if employee_code in getattr(control_horario_service, "active_records", {}):
        try:
            control_horario_service.check_out(
                employee_id=employee_code,
                method=CheckInMethod.REMOTE,
                location="auto_session_close",
            )
        except Exception as e:
            logger.warning("check_out memoria previo: %s", e)

    rows = (
        db.query(TimeTrackingRecord)
        .filter(
            TimeTrackingRecord.user_id == user.id,
            TimeTrackingRecord.employee_id == employee_code,
            TimeTrackingRecord.status == RecordStatus.ACTIVE,
        )
        .all()
    )
    for active in rows:
        _close_tracking_row_at(
            db,
            user=user,
            employee_code=employee_code,
            active=active,
            checkout_time=checkout_time,
            close_reason=reason,
        )

    wss = (
        db.query(EmployeeWorkSession)
        .filter(
            EmployeeWorkSession.user_id == user.id,
            EmployeeWorkSession.status == "active",
        )
        .all()
    )
    for ws in wss:
        ws.status = "superseded" if reason == "duplicate_login" else "closed"
        ws.closed_at = checkout_time
        ws.close_reason = reason
        db.add(ws)

    db.commit()
    sm.sync_runtime_active_records(db, user, control_horario_service)


def begin_work_session_on_login(db: Session, user: User) -> Dict[str, Any]:
    """
    Tras login exitoso: empleado con ficha RRHH → clock-in + employee_work_session.
    Dueños u otros roles: skipped.
    """
    if _user_role(user) != "employee":
        return {"skipped": True, "requires_jornada": False}

    ce: Optional[CompanyEmployee] = session_company_employee(db, user)
    if not ce:
        return {
            "skipped": True,
            "requires_jornada": True,
            "active": False,
            "reason": "no_company_employee",
            "message": "Sin ficha en RRHH vinculada; no se inicia jornada.",
        }

    employee_code = str(ce.employee_code)
    now_ts = datetime.now(timezone.utc)

    existing_ws = _active_work_session(db, user)
    if existing_ws and existing_ws.time_tracking_record_id:
        prev = (
            db.query(TimeTrackingRecord)
            .filter(TimeTrackingRecord.id == existing_ws.time_tracking_record_id)
            .first()
        )
        if prev and prev.status == RecordStatus.ACTIVE:
            existing_ws.last_activity_at = now_ts
            db.add(existing_ws)
            db.commit()
            return {
                "skipped": False,
                "requires_jornada": True,
                "active": True,
                "continued": True,
                "work_session_id": existing_ws.id,
                "time_tracking_record_id": prev.id,
                "employee_code": employee_code,
                "check_in_time": prev.check_in_time.isoformat() if prev.check_in_time else None,
            }

    _close_active_sessions_and_records(
        db, user, employee_code, now_ts, "duplicate_login"
    )

    row = TimeTrackingRecord(
        employee_id=employee_code,
        user_id=user.id,
        check_in_time=now_ts,
        check_in_method=CheckInMethod.REMOTE,
        check_in_location="login_automatico",
        status=RecordStatus.ACTIVE,
        irregularities=[],
        irregularities_count=0,
        is_late_check_in=False,
    )
    db.add(row)
    db.flush()

    sm.append_event(
        db,
        user_id=user.id,
        employee_id=employee_code,
        record_id=row.id,
        event_type="check-in",
        occurred_at=now_ts,
        location="login_automatico",
        latitude=None,
        longitude=None,
        device=None,
        extra_payload={"source": "login"},
    )

    cid = primary_company_id(db, user)
    ews = EmployeeWorkSession(
        user_id=user.id,
        company_id=cid,
        employee_code=employee_code,
        time_tracking_record_id=row.id,
        status="active",
        opened_at=now_ts,
        last_activity_at=now_ts,
    )
    db.add(ews)
    db.commit()
    sm.sync_runtime_active_records(db, user, control_horario_service)

    if getattr(settings, "SMART_TIME_CONTROL_LOG_AFRODITA", True):
        try:
            emit_time_control_event(
                user_id=user.id,
                user_email=user.email,
                company_id=cid,
                employee_id=employee_code,
                event_type="check-in",
                record_id=row.id,
                details={"source": "login_automatico"},
            )
        except Exception:
            logger.exception("emit_time_control_event login jornada")

    return {
        "skipped": False,
        "requires_jornada": True,
        "active": True,
        "work_session_id": ews.id,
        "time_tracking_record_id": row.id,
        "employee_code": employee_code,
        "check_in_time": now_ts.isoformat(),
    }


def _active_work_session(db: Session, user: User) -> Optional[EmployeeWorkSession]:
    return (
        db.query(EmployeeWorkSession)
        .filter(
            EmployeeWorkSession.user_id == user.id,
            EmployeeWorkSession.status == "active",
        )
        .order_by(EmployeeWorkSession.id.desc())
        .first()
    )


def apply_idle_timeout_if_needed(db: Session, user: User) -> None:
    """Si la jornada supera inactividad, cierra fichaje y sesión (servidor)."""
    if _user_role(user) != "employee":
        return
    ws = _active_work_session(db, user)
    if not ws or not ws.last_activity_at:
        return
    now_ts = datetime.now(timezone.utc)
    last = ws.last_activity_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if now_ts - last < _idle_delta():
        return

    ce = session_company_employee(db, user)
    if not ce:
        return
    employee_code = str(ce.employee_code)
    checkout_time = last + _idle_delta()
    rec = (
        db.query(TimeTrackingRecord)
        .filter(TimeTrackingRecord.id == ws.time_tracking_record_id)
        .first()
    )
    if rec and rec.status == RecordStatus.ACTIVE:
        _close_tracking_row_at(
            db,
            user=user,
            employee_code=employee_code,
            active=rec,
            checkout_time=checkout_time,
            close_reason="idle_timeout",
        )
    ws.status = "auto_closed"
    ws.closed_at = checkout_time
    ws.close_reason = "idle_timeout"
    db.add(ws)
    db.commit()
    sm.sync_runtime_active_records(db, user, control_horario_service)


def touch_work_session_activity(db: Session, user: User) -> None:
    """Marca actividad (p. ej. cada request TPV)."""
    if _user_role(user) != "employee":
        return
    ws = _active_work_session(db, user)
    if not ws:
        return
    ws.last_activity_at = datetime.now(timezone.utc)
    db.add(ws)
    db.commit()


def end_work_session_on_logout(db: Session, user: User) -> Dict[str, Any]:
    """Logout: clock-out del registro activo y cierre de employee_work_session."""
    if _user_role(user) != "employee":
        return {"skipped": True}

    ce = session_company_employee(db, user)
    if not ce:
        return {"skipped": True, "reason": "no_company_employee"}

    employee_code = str(ce.employee_code)
    now_ts = datetime.now(timezone.utc)

    sm.sync_runtime_active_records(db, user, control_horario_service)
    ws = _active_work_session(db, user)

    active = (
        db.query(TimeTrackingRecord)
        .filter(
            TimeTrackingRecord.user_id == user.id,
            TimeTrackingRecord.employee_id == employee_code,
            TimeTrackingRecord.status == RecordStatus.ACTIVE,
        )
        .order_by(TimeTrackingRecord.id.desc())
        .first()
    )

    hours = 0.0
    rec_id = active.id if active else None
    if active:
        _close_tracking_row_at(
            db,
            user=user,
            employee_code=employee_code,
            active=active,
            checkout_time=now_ts,
            close_reason="logout",
        )
        hours = float(active.hours_worked or 0)

    if ws:
        ws.status = "closed"
        ws.closed_at = now_ts
        ws.close_reason = "logout"
        db.add(ws)

    db.commit()
    sm.sync_runtime_active_records(db, user, control_horario_service)

    if getattr(settings, "SMART_TIME_CONTROL_LOG_AFRODITA", True) and active and rec_id:
        try:
            emit_time_control_event(
                user_id=user.id,
                user_email=user.email,
                company_id=primary_company_id(db, user),
                employee_id=employee_code,
                event_type="check-out",
                record_id=rec_id,
                details={"hours_worked": hours, "source": "logout"},
            )
        except Exception:
            logger.exception("emit logout jornada")

    return {
        "success": True,
        "hours_worked": hours,
        "employee_code": employee_code,
    }


def get_jornada_status(db: Session, user: User) -> Dict[str, Any]:
    """Estado para /me y UI: En turno / Fuera de turno."""
    role = _user_role(user)
    if role != "employee":
        return {
            "requires_jornada": False,
            "in_turno": True,
            "role": role,
        }

    apply_idle_timeout_if_needed(db, user)

    ce = session_company_employee(db, user)
    if not ce:
        return {
            "requires_jornada": True,
            "in_turno": False,
            "reason": "no_company_employee",
        }

    ws = _active_work_session(db, user)
    if not ws:
        return {
            "requires_jornada": True,
            "in_turno": False,
            "reason": "no_active_session",
        }

    rec = None
    if ws.time_tracking_record_id:
        rec = (
            db.query(TimeTrackingRecord)
            .filter(TimeTrackingRecord.id == ws.time_tracking_record_id)
            .first()
        )
    in_turno = bool(rec and rec.status == RecordStatus.ACTIVE)
    return {
        "requires_jornada": True,
        "in_turno": in_turno,
        "work_session_id": ws.id,
        "time_tracking_record_id": ws.time_tracking_record_id,
        "employee_code": ws.employee_code,
        "check_in_time": rec.check_in_time.isoformat() if rec and rec.check_in_time else None,
        "last_activity_at": ws.last_activity_at.isoformat() if ws.last_activity_at else None,
    }


def get_active_work_session_id_for_sale(db: Session, user: User) -> Optional[int]:
    """ID de jornada para asociar venta TPV (empleado en turno)."""
    st = get_jornada_status(db, user)
    if not st.get("in_turno"):
        return None
    wid = st.get("work_session_id")
    return int(wid) if wid is not None else None


def assert_employee_jornada_for_tpv(db: Session, user: User) -> None:
    """403 si empleado debe trabajar en jornada y no está en turno."""
    from fastapi import HTTPException, status

    if _user_role(user) != "employee":
        return
    st = get_jornada_status(db, user)
    if st.get("reason") == "no_company_employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta de empleado no tiene ficha en RRHH; no puedes usar el TPV.",
        )
    if not st.get("in_turno"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No hay jornada activa. Inicia sesión de nuevo para fichar entrada o espera a que finalice el cierre automático.",
        )
