"""
Control horario inteligente (ROCE): eventos, estado en tiempo real, horas, alertas, TPV.
Mantiene compatibilidad con TimeTrackingRecord y ControlHorarioService en memoria.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company_employee import CompanyEmployee
from app.models.time_tracking import (
    EmployeeSchedule,
    RecordStatus,
    TimeControlAlert,
    TimeControlEvent,
    TimeTrackingRecord,
)
from app.models.user import User
from app.models.company import UserCompany

logger = logging.getLogger(__name__)

EVENT_TYPES = frozenset({"check-in", "check-out", "break-start", "break-end"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today_range_utc() -> Tuple[datetime, datetime]:
    now = _utc_now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _parse_opt_float(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def geo_payload_for_event(
    latitude: Optional[float],
    longitude: Optional[float],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    lat0f = _parse_opt_float(getattr(settings, "CONTROL_HORARIO_OFFICE_LAT", None))
    lon0f = _parse_opt_float(getattr(settings, "CONTROL_HORARIO_OFFICE_LON", None))
    rf = _parse_opt_float(getattr(settings, "CONTROL_HORARIO_OFFICE_RADIUS_M", None))
    if lat0f is None or lon0f is None or rf is None:
        return out
    if latitude is None or longitude is None:
        out["geo_validated"] = True
        out["location_ok"] = False
        out["reason"] = "missing_coordinates"
        return out
    dist = haversine_m(float(latitude), float(longitude), lat0f, lon0f)
    ok = dist <= rf
    out["geo_validated"] = True
    out["location_ok"] = ok
    out["distance_m"] = round(dist, 1)
    out["office_radius_m"] = rf
    fail = getattr(settings, "CONTROL_HORARIO_FAIL_IF_OUTSIDE_ZONE", False)
    out["fail_if_outside"] = bool(fail)
    return out


def today_completed_hours_by_employee(db: Session, user: User) -> Dict[str, float]:
    start, end = _today_range_utc()
    rows = (
        db.query(TimeTrackingRecord)
        .filter(
            TimeTrackingRecord.user_id == user.id,
            TimeTrackingRecord.status == RecordStatus.COMPLETED,
            TimeTrackingRecord.check_in_time >= start,
            TimeTrackingRecord.check_in_time < end,
        )
        .all()
    )
    acc: Dict[str, float] = {}
    for r in rows:
        eid = str(r.employee_id)
        acc[eid] = acc.get(eid, 0.0) + float(r.hours_worked or 0.0)
    return acc


def sync_runtime_active_records(db: Session, user: User, control_horario_service: Any) -> None:
    """Hidrata active_records del servicio desde BD (reinicios / multi-worker)."""
    rows = (
        db.query(TimeTrackingRecord)
        .filter(
            TimeTrackingRecord.user_id == user.id,
            TimeTrackingRecord.status == RecordStatus.ACTIVE,
        )
        .all()
    )
    for r in rows:
        emp = str(r.employee_id)
        method_val = str(
            r.check_in_method.value if hasattr(r.check_in_method, "value") else (r.check_in_method or "code")
        )
        control_horario_service.active_records[emp] = {
            "id": f"record_{emp}_{r.id}",
            "employee_id": emp,
            "user_id": user.id,
            "check_in_time": r.check_in_time,
            "check_in_method": method_val,
            "check_in_location": r.check_in_location or "Oficina Principal",
            "check_in_latitude": r.check_in_latitude,
            "check_in_longitude": r.check_in_longitude,
            "status": "active",
            "irregularities": r.irregularities or [],
            "irregularities_count": int(r.irregularities_count or 0),
            "is_late_check_in": bool(r.is_late_check_in),
            "synced_with_afrodita": bool(r.synced_with_afrodita),
            "synced_with_rafael": bool(r.synced_with_rafael),
            "db_record_id": r.id,
        }


def append_event(
    db: Session,
    *,
    user_id: int,
    employee_id: str,
    record_id: Optional[int],
    event_type: str,
    occurred_at: datetime,
    location: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
    device: Optional[str],
    extra_payload: Optional[Dict[str, Any]] = None,
) -> Optional[TimeControlEvent]:
    if event_type not in EVENT_TYPES:
        logger.warning("Tipo de evento no soportado: %s", event_type)
        return None
    payload = dict(extra_payload or {})
    payload.update(geo_payload_for_event(latitude, longitude))
    ev = TimeControlEvent(
        user_id=user_id,
        employee_id=str(employee_id),
        record_id=record_id,
        event_type=event_type,
        occurred_at=occurred_at,
        location=location,
        latitude=latitude,
        longitude=longitude,
        device=(device or "")[:512] or None,
        payload=payload or None,
    )
    db.add(ev)
    return ev


def events_for_record(
    db: Session, user_id: int, record_id: int, since: datetime, until: datetime
) -> List[TimeControlEvent]:
    return (
        db.query(TimeControlEvent)
        .filter(
            TimeControlEvent.user_id == user_id,
            TimeControlEvent.record_id == record_id,
            TimeControlEvent.occurred_at >= since,
            TimeControlEvent.occurred_at <= until,
        )
        .order_by(TimeControlEvent.occurred_at.asc())
        .all()
    )


def derive_work_status(
    db: Session,
    *,
    user_id: int,
    employee_id: str,
    active_row: Optional[TimeTrackingRecord],
) -> str:
    """
    inside | outside | on_break
    Si hay registro ACTIVE hoy, el último evento tras la entrada decide pausa.
    """
    if not active_row:
        return "outside"
    start, end = _today_range_utc()
    if active_row.check_in_time < start or active_row.check_in_time >= end:
        return "inside" if active_row.status == RecordStatus.ACTIVE else "outside"
    evs = events_for_record(db, user_id, active_row.id, active_row.check_in_time, end)
    last_type = "check-in"
    for e in evs:
        last_type = e.event_type
    if last_type == "break-start":
        return "on_break"
    if last_type == "check-out":
        return "outside"
    return "inside"


def build_employees_smart_status(
    db: Session,
    user: User,
    roster_ids: Optional[List[str]] = None,
) -> Tuple[Dict[str, Dict[str, Any]], int]:
    """
    Mapa employee_id -> {status, check_in_time, record_id?, smart: true}
    total_active: empleados dentro o en pausa (no fuera).
    """
    start, end = _today_range_utc()
    rows = (
        db.query(TimeTrackingRecord)
        .filter(
            TimeTrackingRecord.user_id == user.id,
            TimeTrackingRecord.status == RecordStatus.ACTIVE,
            TimeTrackingRecord.check_in_time >= start,
            TimeTrackingRecord.check_in_time < end,
        )
        .all()
    )
    out: Dict[str, Dict[str, Any]] = {}
    total = 0
    for r in rows:
        eid = str(r.employee_id)
        if roster_ids is not None and eid not in roster_ids:
            continue
        st = derive_work_status(db, user_id=user.id, employee_id=eid, active_row=r)
        out[eid] = {
            "status": st,
            "check_in_time": r.check_in_time.isoformat() if r.check_in_time else None,
            "record_id": r.id,
            "smart": True,
        }
        if st in ("inside", "on_break"):
            total += 1
    return out, total


def merge_today_timeline(db: Session, user: User, base_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Añade eventos break-* del día a la línea temporal mostrada en UI."""
    start, end = _today_range_utc()
    try:
        ev_rows = (
            db.query(TimeControlEvent)
            .filter(
                TimeControlEvent.user_id == user.id,
                TimeControlEvent.occurred_at >= start,
                TimeControlEvent.occurred_at < end,
                TimeControlEvent.event_type.in_(["break-start", "break-end"]),
            )
            .order_by(TimeControlEvent.occurred_at.desc())
            .limit(200)
            .all()
        )
    except Exception as e:
        logger.warning("merge_today_timeline omitido: %s", e)
        return base_records
    extra: List[Dict[str, Any]] = []
    for e in ev_rows:
        extra.append(
            {
                "id": f"ev-{e.id}",
                "employee_id": str(e.employee_id),
                "type": e.event_type,
                "time": e.occurred_at.isoformat() if e.occurred_at else None,
                "method": "event",
                "record_id": e.record_id,
            }
        )
    merged = list(base_records) + extra
    merged.sort(key=lambda x: str(x.get("time") or ""), reverse=True)
    return merged


def _parse_hhmm(s: str) -> Tuple[int, int]:
    parts = str(s).strip().split(":")
    h = int(parts[0]) if parts else 0
    m = int(parts[1]) if len(parts) > 1 else 0
    return h, m


def expected_hours_today_for_employee(db: Session, user: Optional[User], employee_id: str) -> float:
    if user is None:
        return 8.0
    dow = _utc_now().weekday()  # 0=Mon
    sch = (
        db.query(EmployeeSchedule)
        .filter(
            EmployeeSchedule.user_id == user.id,
            EmployeeSchedule.employee_id == str(employee_id),
            EmployeeSchedule.day_of_week == dow,
            EmployeeSchedule.is_active.is_(True),
        )
        .first()
    )
    if not sch:
        return 8.0
    sh, sm = _parse_hhmm(str(sch.start_time))
    eh, em = _parse_hhmm(str(sch.end_time))
    start_m = sh * 60 + sm
    end_m = eh * 60 + em
    if end_m <= start_m:
        return 8.0
    return (end_m - start_m) / 60.0


def compute_hours_with_break_events(
    db: Session,
    *,
    user_id: int,
    record: TimeTrackingRecord,
    check_out_time: datetime,
    fallback_break_hours: float,
) -> Tuple[float, float, float]:
    """
    Retorna (hours_worked_neto, break_hours, extra_hours).
    """
    cin = record.check_in_time
    if cin.tzinfo is None:
        cin = cin.replace(tzinfo=timezone.utc)
    if check_out_time.tzinfo is None:
        check_out_time = check_out_time.replace(tzinfo=timezone.utc)
    gross = max(0.0, (check_out_time - cin).total_seconds() / 3600.0)
    evs = events_for_record(db, user_id, record.id, cin, check_out_time)
    break_h = 0.0
    open_break: Optional[datetime] = None
    for e in evs:
        if e.event_type == "break-start":
            open_break = e.occurred_at
        elif e.event_type == "break-end" and open_break is not None:
            break_h += max(0.0, (e.occurred_at - open_break).total_seconds() / 3600.0)
            open_break = None
    if open_break is not None:
        break_h += max(0.0, (check_out_time - open_break).total_seconds() / 3600.0)
    if break_h <= 0 and fallback_break_hours > 0:
        break_h = fallback_break_hours
    net = max(0.0, gross - break_h)
    u = db.query(User).filter(User.id == user_id).first()
    exp = expected_hours_today_for_employee(db, u, str(record.employee_id)) if u else 8.0
    extra = max(0.0, net - exp)
    return round(net, 2), round(break_h, 2), round(extra, 2)


def _company_ids(db: Session, user: User) -> List[int]:
    rows = db.query(UserCompany.company_id).filter(UserCompany.user_id == user.id).all()
    return [r[0] for r in rows]


def tpv_sales_window(db: Session, user: User, hours: float = 4.0) -> Dict[str, Any]:
    """Agregado simple de ventas recientes para sugerencias de staffing (TPV)."""
    try:
        from app.models.erp import TPVSale
    except Exception:
        return {"ok": False, "reason": "tpv_model_unavailable"}
    since = _utc_now() - timedelta(hours=hours)
    q = (
        db.query(func.coalesce(func.sum(TPVSale.total), 0))
        .filter(TPVSale.user_id == user.id, TPVSale.sale_date >= since)
        .scalar()
    )
    total = float(q or 0)
    baseline_since = _utc_now() - timedelta(days=7)
    days = max(1, 7)
    daily_avg = (
        db.query(func.coalesce(func.sum(TPVSale.total), 0))
        .filter(TPVSale.user_id == user.id, TPVSale.sale_date >= baseline_since)
        .scalar()
    )
    avg = float(daily_avg or 0) / days
    window_equiv_daily = total * (24.0 / max(0.01, hours))
    high = float(settings.CONTROL_HORARIO_TPV_HIGH_RATIO)
    low = float(settings.CONTROL_HORARIO_TPV_LOW_RATIO)
    hint = "steady"
    if avg > 0 and window_equiv_daily > avg * float(high):
        hint = "increase_staffing"
    elif avg > 0 and window_equiv_daily < avg * float(low):
        hint = "reduce_staffing"
    return {
        "ok": True,
        "window_hours": hours,
        "window_sales_total": round(total, 2),
        "daily_avg_7d": round(avg, 2),
        "staffing_hint": hint,
    }


def detect_patterns(db: Session, user: User, employee_ids: List[str]) -> Dict[str, Any]:
    since = _utc_now() - timedelta(days=14)
    out: Dict[str, Any] = {"retrasos": {}, "horas_extra_recurrentes": {}, "ausencias_proxies": {}}
    for eid in employee_ids:
        late = (
            db.query(func.count(TimeTrackingRecord.id))
            .filter(
                TimeTrackingRecord.user_id == user.id,
                TimeTrackingRecord.employee_id == str(eid),
                TimeTrackingRecord.check_in_time >= since,
                TimeTrackingRecord.is_late_check_in.is_(True),
            )
            .scalar()
        )
        out["retrasos"][eid] = int(late or 0)
        extra_days = (
            db.query(func.count(TimeTrackingRecord.id))
            .filter(
                TimeTrackingRecord.user_id == user.id,
                TimeTrackingRecord.employee_id == str(eid),
                TimeTrackingRecord.check_in_time >= since,
                TimeTrackingRecord.extra_hours.isnot(None),
                TimeTrackingRecord.extra_hours > 1.0,
            )
            .scalar()
        )
        out["horas_extra_recurrentes"][eid] = int(extra_days or 0)
        completed = (
            db.query(func.count(TimeTrackingRecord.id))
            .filter(
                TimeTrackingRecord.user_id == user.id,
                TimeTrackingRecord.employee_id == str(eid),
                TimeTrackingRecord.check_in_time >= since,
                TimeTrackingRecord.status == RecordStatus.COMPLETED,
            )
            .scalar()
        )
        out["ausencias_proxies"][eid] = {"completed_segments_14d": int(completed or 0)}
    return out


def _recent_alert_exists(
    db: Session, user_id: int, kind: str, employee_id: Optional[str], within_minutes: int = 120
) -> bool:
    since = _utc_now() - timedelta(minutes=within_minutes)
    q = db.query(TimeControlAlert.id).filter(
        TimeControlAlert.user_id == user_id,
        TimeControlAlert.alert_kind == kind,
        TimeControlAlert.created_at >= since,
    )
    if employee_id:
        q = q.filter(TimeControlAlert.employee_id == str(employee_id))
    return q.first() is not None


def persist_alert(
    db: Session,
    *,
    user_id: int,
    employee_id: Optional[str],
    alert_kind: str,
    message: str,
    severity: str = "warning",
    details: Optional[Dict[str, Any]] = None,
    targets: Optional[List[str]] = None,
) -> None:
    if _recent_alert_exists(db, user_id, alert_kind, employee_id):
        return
    db.add(
        TimeControlAlert(
            user_id=user_id,
            employee_id=str(employee_id) if employee_id else None,
            alert_kind=alert_kind,
            message=message,
            severity=severity,
            details=details,
            notify_targets=targets or ["admin", "manager"],
        )
    )


def evaluate_alerts(
    db: Session,
    user: User,
    *,
    roster: List[Dict[str, Any]],
    employees_status: Dict[str, Dict[str, Any]],
    max_hours_soft: float = 12.0,
) -> List[Dict[str, Any]]:
    """Evalúa reglas ROCE y persiste alertas deduplicadas."""
    grace = int(getattr(settings, "CONTROL_HORARIO_ALERT_GRACE_MINUTES", 15) or 15)
    now = _utc_now()
    dow = now.weekday()
    alerts_out: List[Dict[str, Any]] = []

    for emp in roster:
        eid = str(emp.get("id") or "")
        if not eid:
            continue
        sch = (
            db.query(EmployeeSchedule)
            .filter(
                EmployeeSchedule.user_id == user.id,
                EmployeeSchedule.employee_id == eid,
                EmployeeSchedule.day_of_week == dow,
                EmployeeSchedule.is_active.is_(True),
            )
            .first()
        )
        st = (employees_status.get(eid) or {}).get("status", "outside")
        if sch:
            sh, sm = _parse_hhmm(str(sch.start_time))
            start_dt = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
            if now > start_dt + timedelta(minutes=grace) and st == "outside":
                persist_alert(
                    db,
                    user_id=user.id,
                    employee_id=eid,
                    alert_kind="empleado_no_ficha",
                    message=f"Sin fichaje tras inicio de turno ({sch.start_time} + {grace}m): {eid}",
                    severity="warning",
                    details={"schedule_start": str(sch.start_time), "grace_min": grace},
                )
                alerts_out.append({"kind": "empleado_no_ficha", "employee_id": eid, "severity": "warning"})

        active = (
            db.query(TimeTrackingRecord)
            .filter(
                TimeTrackingRecord.user_id == user.id,
                TimeTrackingRecord.employee_id == eid,
                TimeTrackingRecord.status == RecordStatus.ACTIVE,
            )
            .order_by(TimeTrackingRecord.id.desc())
            .first()
        )
        if active and active.check_in_time:
            if active.check_in_time.tzinfo is None:
                ci = active.check_in_time.replace(tzinfo=timezone.utc)
            else:
                ci = active.check_in_time
            hours_open = (now - ci).total_seconds() / 3600.0
            if hours_open > max_hours_soft:
                persist_alert(
                    db,
                    user_id=user.id,
                    employee_id=eid,
                    alert_kind="exceso_horas",
                    message=f"Fichaje abierto {round(hours_open, 1)}h (umbral {max_hours_soft}h)",
                    severity="critical",
                    details={"hours_open": round(hours_open, 2)},
                )
                alerts_out.append({"kind": "exceso_horas", "employee_id": eid, "severity": "critical"})

    company_ids = _company_ids(db, user)
    if company_ids:
        n_roster = (
            db.query(func.count(CompanyEmployee.id))
            .filter(
                CompanyEmployee.company_id.in_(company_ids),
                CompanyEmployee.is_active.is_(True),
            )
            .scalar()
        ) or 0
        n_inside = sum(1 for _eid, st in employees_status.items() if st.get("status") in ("inside", "on_break"))
        if n_roster > 0 and n_inside == 0 and 8 <= now.hour <= 22:
            persist_alert(
                db,
                user_id=user.id,
                employee_id=None,
                alert_kind="turno_sin_cubrir",
                message="Nadie fichado dentro; revisar cobertura de turno.",
                severity="warning",
                details={"roster_count": int(n_roster)},
            )
            alerts_out.append({"kind": "turno_sin_cubrir", "severity": "warning"})

    try:
        db.flush()
    except Exception:
        logger.exception("flush tras evaluate_alerts")
    return alerts_out


def fetch_recent_alerts(db: Session, user: User, limit: int = 30) -> List[Dict[str, Any]]:
    since = _utc_now() - timedelta(hours=48)
    rows = (
        db.query(TimeControlAlert)
        .filter(TimeControlAlert.user_id == user.id, TimeControlAlert.created_at >= since)
        .order_by(TimeControlAlert.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "kind": r.alert_kind,
            "message": r.message,
            "severity": r.severity,
            "employee_id": r.employee_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "targets": r.notify_targets or ["admin", "manager"],
        }
        for r in rows
    ]


def validate_break_transition(db: Session, user_id: int, record: TimeTrackingRecord, want: str) -> None:
    """Raises ValueError si la transición break no es válida."""
    evs = events_for_record(db, user_id, record.id, record.check_in_time, _utc_now() + timedelta(days=1))
    last = "check-in"
    for e in evs:
        last = e.event_type
    if want == "break-start":
        if last == "break-start":
            raise ValueError("Ya en pausa")
        if last == "check-out":
            raise ValueError("Registro cerrado")
    elif want == "break-end":
        if last != "break-start":
            raise ValueError("No hay pausa abierta")
