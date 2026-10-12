"""AFRODITA: consultas reales para el chat/voz (fichajes de hoy y agenda de hoy) de la empresa.

Fichajes: solo se leen registros de `time_tracking_records` de la empresa (horas, estados,
incidencias). NO se leen ni procesan datos biometricos (ni imagen ni metodo facial): el resumen
es el mismo sea cual sea el metodo con el que se fichó.

Agenda: reservas del dia (`reservations`, hosteleria) y reuniones con leads (`crm_leads.meeting_at`,
oficina). Si una empresa no usa una de las dos, esa parte sale vacia: no se rellena con nada.

Pedidos: ZEUS no tiene modelo de pedidos (ni de clientes ni a proveedores). `ORDERS_NOT_AVAILABLE`
es el motivo honesto que devuelve el ejecutor en vez de inventarlos.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from services.local_day_v1 import day_bounds_utc, local_tz

ORDERS_NOT_AVAILABLE = (
    "ZEUS todavía no tiene un registro de pedidos (ni de clientes ni a proveedores), así que no puedo "
    "decirte los pedidos de esta semana sin inventarlos. Puedo darte las ventas del TPV, el cierre de "
    "un día o el estado del inventario."
)


def attendance_today(db: Session, company_id: int, day: date) -> Dict[str, Any]:
    from app.models.time_tracking import RecordStatus, TimeTrackingRecord

    start, end = day_bounds_utc(day)
    base = db.query(TimeTrackingRecord).filter(TimeTrackingRecord.company_id == company_id)
    today = base.filter(TimeTrackingRecord.check_in_time >= start, TimeTrackingRecord.check_in_time < end).all()
    inside = base.filter(
        TimeTrackingRecord.check_out_time.is_(None), TimeTrackingRecord.status == RecordStatus.ACTIVE
    ).all()
    return {
        "date": day.isoformat(),
        "timezone": local_tz()[1],
        "checkins_today": len(today),
        "employees_today": len({r.employee_id for r in today}),
        "currently_in": len({r.employee_id for r in inside}),
        "late_today": sum(1 for r in today if r.is_late_check_in),
        "with_irregularities_today": sum(1 for r in today if (r.irregularities_count or 0) > 0),
        "hours_closed_today": round(sum(float(r.hours_worked or 0) for r in today if r.check_out_time), 2),
        "biometric_data_used": False,
        "source": "time_tracking_records",
    }


def agenda_today(db: Session, company_id: int, day: date, *, limit: int = 10) -> Dict[str, Any]:
    from app.models.crm_lead import CrmLead
    from app.models.reservation import Reservation

    res = (
        db.query(Reservation)
        .filter(
            Reservation.company_id == company_id,
            Reservation.reservation_date == day,
            Reservation.status.notin_(("cancelled", "no_show")),
        )
        .order_by(Reservation.reservation_time.asc())
        .all()
    )
    start, end = day_bounds_utc(day)
    tz, tz_name = local_tz()
    meetings = (
        db.query(CrmLead)
        .filter(
            CrmLead.company_id == company_id,
            CrmLead.status == "open",
            CrmLead.meeting_at >= start,
            CrmLead.meeting_at < end,
        )
        .order_by(CrmLead.meeting_at.asc())
        .all()
    )

    def _hhmm(dt) -> str:
        if dt.tzinfo is None:  # SQLite devuelve naive (UTC)
            from datetime import timezone

            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz).strftime("%H:%M")

    items: List[Dict[str, Any]] = [
        {"kind": "reservation", "time": r.reservation_time, "guests": r.num_guests, "name": r.guest_name,
         "status": r.status}
        for r in res
    ] + [{"kind": "meeting", "time": _hhmm(m.meeting_at), "name": m.name} for m in meetings]
    items.sort(key=lambda i: i["time"] or "")
    return {
        "date": day.isoformat(),
        "timezone": tz_name,
        "reservations": len(res),
        "guests": sum(int(r.num_guests or 0) for r in res),
        "meetings": len(meetings),
        "items": items[:limit],
        "source": "reservations+crm_leads",
    }
