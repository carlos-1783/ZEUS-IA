"""
AFRODITA workspace RRHH v1 — conecta UI a company_employees, employee_schedules y register_checkin.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.company import UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.time_tracking import (
    DEFAULT_SCHEDULE_DAYS,
    DEFAULT_SCHEDULE_END,
    DEFAULT_SCHEDULE_SHIFT,
    DEFAULT_SCHEDULE_START,
    EmployeeSchedule,
)
from app.models.user import User
from services.afrodita_unified_control import (
    DAY_NAMES,
    can_create_employee,
    can_execute_checkin,
    current_flags,
    log_execution_attempt,
    validate_qr_freshness,
)
from services.workspace_deliverables import primary_company_id_for_user

logger = logging.getLogger(__name__)


def _company_ids_for_user(db: Session, user: User) -> List[int]:
    rows = db.query(UserCompany.company_id).filter(UserCompany.user_id == user.id).all()
    return [int(r[0]) for r in rows]


def employee_exists(db: Session, *, company_id: int, employee_code: str) -> bool:
    return (
        db.query(CompanyEmployee.id)
        .filter(
            CompanyEmployee.company_id == company_id,
            CompanyEmployee.employee_code == str(employee_code),
            CompanyEmployee.is_active.is_(True),
        )
        .first()
        is not None
    )


def list_company_employees(db: Session, user: User) -> Dict[str, Any]:
    flags = current_flags()
    if not flags["AFRODITA_USE_REAL_EMPLOYEES"]:
        return {
            "employees": [],
            "count": 0,
            "source": "disabled",
            "read_only": True,
        }

    company_ids = _company_ids_for_user(db, user)
    if not company_ids:
        return {"employees": [], "count": 0, "source": "company_employees", "read_only": True}

    rows = (
        db.query(CompanyEmployee)
        .filter(
            CompanyEmployee.company_id.in_(company_ids),
            CompanyEmployee.is_active.is_(True),
        )
        .order_by(CompanyEmployee.full_name.asc())
        .all()
    )
    employees = [
        {
            "id": r.id,
            "employee_code": str(r.employee_code),
            "full_name": r.full_name,
            "role_title": r.role_title or "",
            "company_id": r.company_id,
            "phone": r.phone,
            "source": r.source or "database",
        }
        for r in rows
    ]
    return {
        "employees": employees,
        "count": len(employees),
        "source": "company_employees",
        "read_only": not can_create_employee(),
    }


def _employee_to_dict(row: CompanyEmployee) -> Dict[str, Any]:
    return {
        "id": row.id,
        "employee_code": str(row.employee_code),
        "full_name": row.full_name,
        "role_title": row.role_title or "",
        "company_id": row.company_id,
        "phone": row.phone,
        "source": row.source or "database",
    }


def create_company_employee(
    db: Session,
    user: User,
    *,
    full_name: str,
    employee_code: str,
    role_title: Optional[str] = None,
    phone: Optional[str] = None,
    hourly_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """Inserta fila real en company_employees — sin mock ni plantillas."""
    if not can_create_employee():
        raise HTTPException(
            status_code=403,
            detail=(
                "Creación de empleados requiere AFRODITA_EXECUTION_ENABLED=true "
                "y AFRODITA_READ_ONLY_MODE=false"
            ),
        )

    flags = current_flags()
    if not flags["AFRODITA_USE_REAL_EMPLOYEES"]:
        raise HTTPException(status_code=503, detail="AFRODITA_USE_REAL_EMPLOYEES=false")

    company_id = primary_company_id_for_user(db, user)
    if not company_id:
        raise HTTPException(status_code=404, detail="Usuario sin empresa asociada")

    name = (full_name or "").strip()
    code = (employee_code or "").strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="full_name requerido (mín. 2 caracteres)")
    if len(code) < 2:
        raise HTTPException(status_code=422, detail="employee_code requerido (mín. 2 caracteres)")

    dup = (
        db.query(CompanyEmployee.id)
        .filter(
            CompanyEmployee.company_id == company_id,
            CompanyEmployee.employee_code == code,
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=409, detail=f"employee_code {code} ya existe en la empresa")

    emp = CompanyEmployee(
        company_id=company_id,
        full_name=name[:255],
        role_title=(role_title or "").strip()[:100] or None,
        employee_code=code[:80],
        phone=(phone or "").strip()[:32] or None,
        hourly_rate=float(hourly_rate or 0.0),
        is_active=True,
        source="afrodita_rrhh_v1",
    )
    db.add(emp)
    db.flush()
    db.refresh(emp)

    log_execution_attempt(
        domain="rrhh",
        action="create_employee",
        allowed=True,
        actor_id=user.id,
    )

    try:
        from services.zeus_event_bus_v1 import emit_event

        emit_event(
            db,
            user,
            event_name="employee_created",
            source_module="AFRODITA",
            payload={"employee": _employee_to_dict(emp), "owner_agent": "AFRODITA"},
        )
    except Exception:
        pass

    return {
        "employee": _employee_to_dict(emp),
        "message": f"Empleado {emp.full_name} creado ({emp.employee_code}).",
    }


def list_employee_schedules(db: Session, user: User) -> Dict[str, Any]:
    flags = current_flags()
    if not flags["AFRODITA_USE_REAL_SCHEDULES"]:
        return {
            "schedules": [],
            "count": 0,
            "source": "employee_schedules",
            "read_only": True,
            "note": "AFRODITA_USE_REAL_SCHEDULES=false — activar flag para lectura real.",
        }

    company_ids = _company_ids_for_user(db, user)
    if not company_ids:
        return {"schedules": [], "count": 0, "source": "employee_schedules", "read_only": True}

    emp_codes = {
        str(r.employee_code)
        for r in db.query(CompanyEmployee.employee_code)
        .filter(
            CompanyEmployee.company_id.in_(company_ids),
            CompanyEmployee.is_active.is_(True),
        )
        .all()
    }
    if not emp_codes:
        return {"schedules": [], "count": 0, "source": "employee_schedules", "read_only": True}

    rows = (
        db.query(EmployeeSchedule)
        .filter(
            EmployeeSchedule.user_id == user.id,
            EmployeeSchedule.employee_id.in_(list(emp_codes)),
            EmployeeSchedule.is_active.is_(True),
        )
        .order_by(EmployeeSchedule.employee_id.asc(), EmployeeSchedule.day_of_week.asc())
        .all()
    )
    schedules = [
        {
            "employee_id": str(r.employee_id),
            "day_of_week": r.day_of_week,
            "day_name": DAY_NAMES[r.day_of_week] if 0 <= r.day_of_week < 7 else str(r.day_of_week),
            "start_time": r.start_time,
            "end_time": r.end_time,
            "shift_type": r.shift_type,
            "location": r.location,
            "break_start": r.break_start,
            "break_duration": r.break_duration,
        }
        for r in rows
    ]
    return {
        "schedules": schedules,
        "count": len(schedules),
        "source": "employee_schedules",
        "read_only": True,
    }


# --- Cuadrante semanal para el chat (AFRODITA · get_staff_schedule) ---------------------------------------
# A diferencia de `list_company_employees` / `list_employee_schedules` (todas las empresas del usuario, para
# el panel RRHH), el chat trabaja SOLO con la empresa de la sesion (company_id resuelto en servidor).
#
# `employee_schedules` no tiene company_id (BD legacy, sin migracion): un horario se atribuye a la empresa
# si su employee_id es el employee_code de un empleado activo de ESA empresa y lo guardo un usuario
# vinculado a ESA empresa. Como employee_code solo es unico DENTRO de una empresa (el alta pone
# `U{user.id}-OWNER` al titular en TODAS sus empresas), un codigo que tambien esta activo en otra empresa
# de esos mismos usuarios es AMBIGUO: sus horarios no se atribuyen a nadie y se pide el dato.
#
# Estado de cada empleado en el cuadrante:
#   "custom"    -> turnos guardados que no son el horario base: se muestran como cuadrante.
#   "default"   -> solo el horario base que pone el sistema al darlo de alta (DEFAULT_SCHEDULE_*): no es
#                  un turno decidido; se dice asi y se piden los turnos reales.
#   "ambiguous" -> su codigo existe en otra empresa del mismo titular: no se puede saber cual es de esta.
#   "none"      -> sin ningun horario guardado.

_MAX_STAFF = 200
_SHIFT_ES = {"manana": "mañana", "mañana": "mañana", "tarde": "tarde", "noche": "noche",
             "completo": "jornada completa", "partido": "turno partido"}
# Puestos guardados como identificador interno en ingles (el alta del titular pone "owner"; la importacion
# de plantilla pone "employee" si no se indica). "" = no aporta nada: se omite.
_ROLE_ES = {"owner": "titular", "manager": "encargado", "admin": "administrador", "administrator": "administrador",
            "employee": "", "staff": "", "worker": "", "user": ""}
_DAY_INDEX = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}


def _role_es(role: Optional[str]) -> str:
    r = (role or "").strip()
    return _ROLE_ES.get(r.lower(), r)


def _hhmm_minutes(v: Optional[str]) -> Optional[int]:
    try:
        hh, mm = str(v or "").strip().split(":")[:2]
        h, m = int(hh), int(mm)
    except (ValueError, TypeError):
        return None
    return h * 60 + m if 0 <= h <= 24 and 0 <= m < 60 else None


def _slot_minutes(r: EmployeeSchedule) -> Optional[int]:
    """Minutos programados del tramo (fin - inicio; nocturno si cruza medianoche), menos el descanso
    solo si tiene hora de descanso guardada. Hora ilegible -> None (no se adivina)."""
    ini, fin = _hhmm_minutes(r.start_time), _hhmm_minutes(r.end_time)
    if ini is None or fin is None:
        return None
    mins = fin - ini if fin > ini else fin + 24 * 60 - ini
    if r.break_start and r.break_duration:
        mins -= int(r.break_duration)
    return max(mins, 0)


def _y_join(names: List[str]) -> str:
    """«Ana, Carlos, Carmelo e Ismael» (conjuncion «e» ante i-/hi-)."""
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    last = names[-1]
    low = last.lower()
    conj = "e" if (low.startswith("i") or (low.startswith("hi") and not low.startswith(("hia", "hie", "hio")))) else "y"
    return f"{', '.join(names[:-1])} {conj} {last}"


def _days_label(days: List[int]) -> str:
    """[0..4] -> «lunes a viernes»; [5, 6] -> «sábado y domingo»; sueltos -> «lunes, miércoles y viernes»."""
    runs: List[List[int]] = []
    for d in sorted(days):
        if runs and d == runs[-1][-1] + 1:
            runs[-1].append(d)
        else:
            runs.append([d])
    parts: List[str] = []
    for run in runs:
        names = [DAY_NAMES[d].lower() for d in run]
        if len(run) >= 3:
            parts.append(f"{names[0]} a {names[-1]}")
        else:
            parts.extend(names)
    return _y_join(parts)


def _slot_txt(start: str, end: str, shift: Optional[str]) -> str:
    s = _SHIFT_ES.get((shift or "").strip().lower(), (shift or "").strip())
    return f"{start}-{end}" + (f" ({s})" if s else "")


_DEFAULT_SLOTS = frozenset(
    (d, DEFAULT_SCHEDULE_START, DEFAULT_SCHEDULE_END, DEFAULT_SCHEDULE_SHIFT) for d in DEFAULT_SCHEDULE_DAYS
)
DEFAULT_SCHEDULE_LABEL = (f"{_days_label(list(DEFAULT_SCHEDULE_DAYS))} "
                          f"{DEFAULT_SCHEDULE_START}-{DEFAULT_SCHEDULE_END}")


def resolve_schedule_day(day: Optional[str], today: date) -> Optional[date]:
    """«today» o un dia de la semana (lunes…domingo, sin acentos) -> fecha (hoy o el proximo). None si no hay
    dia. Valor desconocido -> ValueError."""
    if day in (None, ""):
        return None
    if day == "today":
        return today
    if day not in _DAY_INDEX:
        raise ValueError("dia no valido")
    return today + timedelta(days=(_DAY_INDEX[day] - today.weekday()) % 7)


def active_employee_names_for_session(db: Session, user: User) -> List[str]:
    """Nombres de los empleados activos de la empresa de la SESION (contexto del bloqueo de ordenes sobre
    horarios: «cambia el horario de Ana» solo es de la plantilla si Ana es empleada). Sin empresa -> []."""
    cid = primary_company_id_for_user(db, user)
    if not cid:
        return []
    return [
        str(r[0]) for r in db.query(CompanyEmployee.full_name)
        .filter(CompanyEmployee.company_id == int(cid), CompanyEmployee.is_active.is_(True))
        .limit(_MAX_STAFF).all()
    ]


def company_staff_schedule(db: Session, company_id: int, today: date, *, week: str = "current",
                           day: Optional[date] = None, employee: Optional[str] = None) -> Dict[str, Any]:
    """Cuadrante REAL de UNA empresa: empleados activos + sus horarios guardados (ver estados arriba).

    - `week`: "current" (semana que empieza hoy) o "next" (la que empieza dentro de 7 dias); solo cambia que
      horarios estan vigentes (`valid_from`/`valid_until`): los turnos guardados son semanales.
    - `day`: fecha concreta -> ademas `schedule_day` con quien trabaja y quien libra ese dia (solo turnos
      decididos; el horario base, los ambiguos y los que no tienen horario se dicen aparte).
    - `missing`: "employees" (no hay empleados), "schedules" (alguno sin turno decidido) o None.
    Nunca rellena huecos ni inventa turnos.
    """
    flags = current_flags()
    if not flags["AFRODITA_USE_REAL_EMPLOYEES"]:
        raise HTTPException(status_code=503, detail="AFRODITA_USE_REAL_EMPLOYEES=false: lectura de empleados desactivada")
    if not flags["AFRODITA_USE_REAL_SCHEDULES"]:
        raise HTTPException(status_code=503, detail="AFRODITA_USE_REAL_SCHEDULES=false: lectura de horarios desactivada")
    if week not in ("current", "next"):
        raise ValueError("semana no valida")

    cid = int(company_id)
    employees = (
        db.query(CompanyEmployee)
        .filter(CompanyEmployee.company_id == cid, CompanyEmployee.is_active.is_(True))
        .order_by(CompanyEmployee.full_name.asc(), CompanyEmployee.id.asc())
        .limit(_MAX_STAFF)
        .all()
    )
    employee_query: Optional[str] = None
    if employee is not None:
        # Consulta de UN empleado: el nombre se resuelve AQUI contra la plantilla activa de esta empresa
        # (nombre completo o de pila, sin acentos/mayusculas). Nunca un id del cliente. Varios con el mismo
        # nombre -> se devuelven todos (no se elige uno). Ninguno -> lista vacia (el texto lo dice).
        from services.intent_parser import fold

        employee_query = fold(" ".join(str(employee).split()))
        if not employee_query:
            raise ValueError("empleado no valido")

        def _match(e: CompanyEmployee) -> bool:
            full = fold(" ".join((e.full_name or "").split()))
            return full == employee_query or full.split(" ")[0] == employee_query

        employees = [e for e in employees if _match(e)]
    by_code = {str(e.employee_code): e for e in employees}
    rows: List[EmployeeSchedule] = []
    ambiguous_codes: set[str] = set()
    if by_code:
        company_users = {
            int(r[0]) for r in db.query(UserCompany.user_id).filter(UserCompany.company_id == cid).all()
        }
        if company_users:
            rows = (
                db.query(EmployeeSchedule)
                .filter(
                    EmployeeSchedule.employee_id.in_(list(by_code)),
                    EmployeeSchedule.user_id.in_(list(company_users)),
                    EmployeeSchedule.is_active.is_(True),
                    EmployeeSchedule.day_of_week >= 0,
                    EmployeeSchedule.day_of_week <= 6,
                )
                .order_by(EmployeeSchedule.day_of_week.asc(), EmployeeSchedule.start_time.asc())
                .all()
            )
            # Otras empresas de los usuarios de esta empresa y de los que guardaron estos horarios: si el
            # mismo employee_code esta activo alli, el horario puede ser de esa otra empresa.
            owners = company_users | {int(r.user_id) for r in rows if r.user_id is not None}
            other_cids = {
                int(r[0]) for r in db.query(UserCompany.company_id)
                .filter(UserCompany.user_id.in_(list(owners)), UserCompany.company_id != cid).all()
            }
            if other_cids:
                # Activo en otra empresa -> ambiguo. Dado de baja alli -> ambiguo solo si hay horarios guardados
                # con ese codigo por usuarios de ESA empresa (el horario puede ser de cuando trabajaba alli).
                for code, other_cid, active in db.query(
                    CompanyEmployee.employee_code, CompanyEmployee.company_id, CompanyEmployee.is_active
                ).filter(
                    CompanyEmployee.company_id.in_(list(other_cids)),
                    CompanyEmployee.employee_code.in_(list(by_code)),
                ).all():
                    code = str(code)
                    if code in ambiguous_codes:
                        continue
                    if active:
                        ambiguous_codes.add(code)
                        continue
                    other_users = [
                        int(r[0]) for r in db.query(UserCompany.user_id)
                        .filter(UserCompany.company_id == int(other_cid)).all()
                    ]
                    if other_users and db.query(EmployeeSchedule.id).filter(
                        EmployeeSchedule.employee_id == code,
                        EmployeeSchedule.user_id.in_(other_users),
                    ).first() is not None:
                        ambiguous_codes.add(code)

    ref = today + timedelta(days=7 if week == "next" else 0)
    lo, hi = (day, day) if day is not None else (ref, ref + timedelta(days=6))
    rows = [
        r for r in rows
        if not (r.valid_until is not None and r.valid_until.date() < lo)
        and not (r.valid_from is not None and r.valid_from.date() > hi)
    ]

    raw: Dict[str, set] = {}
    for r in rows:
        raw.setdefault(str(r.employee_id), set()).add(
            (int(r.day_of_week), str(r.start_time), str(r.end_time), (r.shift_type or "").strip().lower() or None)
        )
    minutes: Dict[str, Optional[int]] = {}
    for r in rows:
        code = str(r.employee_id)
        if code in minutes and minutes[code] is None:
            continue
        m = _slot_minutes(r)
        minutes[code] = None if m is None else (minutes.get(code) or 0) + m

    roster: List[Dict[str, Any]] = []
    default_only: List[str] = []
    ambiguous: List[str] = []
    without: List[str] = []
    custom_days: Dict[int, Dict[int, List[str]]] = {}  # por id de empleado (puede haber nombres repetidos)
    name_of: Dict[int, str] = {e.id: e.full_name for e in employees}
    for e in employees:
        code = str(e.employee_code)
        slots = raw.get(code)
        if slots and code in ambiguous_codes:
            ambiguous.append(e.full_name)
            continue
        if not slots:
            without.append(e.full_name)
            continue
        if slots == _DEFAULT_SLOTS:
            default_only.append(e.full_name)
            continue
        days: Dict[int, List[str]] = {}
        for d, ini, fin, shift in sorted(slots):
            days.setdefault(d, []).append(_slot_txt(ini, fin, shift))
        custom_days[e.id] = days
        groups: Dict[str, List[int]] = {}
        for d, txts in days.items():
            groups.setdefault(" y ".join(txts), []).append(d)
        week_txt = "; ".join(f"{_days_label(ds)} {txt}" for txt, ds in sorted(groups.items(), key=lambda kv: min(kv[1])))
        mins = minutes.get(code)
        roster.append({
            "name": e.full_name,
            "role_title": _role_es(e.role_title),
            "shift_week": week_txt,
            "hours_week": round(mins / 60, 2) if mins is not None else None,
        })

    undecided = bool(default_only or ambiguous or without)
    covered = {d for days in custom_days.values() for d in days}
    result: Dict[str, Any] = {
        "company_id": cid,
        "schedule_week": week,
        "employees_total": len(employees),
        "employees_with_schedule": len(roster),
        "shifts_count": sum(len(t) for days in custom_days.values() for t in days.values()),
        "roster": roster,
        "default_schedule_only": default_only,
        "ambiguous_schedule": ambiguous,
        "without_schedule": without,
        "uncovered_days": ([DAY_NAMES[d].lower() for d in range(7) if d not in covered]
                           if roster and not undecided else []),
        "missing": "employees" if not employees else ("schedules" if undecided else None),
        "source": "company_employees+employee_schedules",
    }
    if employee_query is not None:
        result["employee_query"] = str(employee).strip()
        result["uncovered_days"] = []
    if day is not None:
        dow = day.weekday()
        result["schedule_day"] = {
            "date": day.isoformat(),
            "schedule_day_name": DAY_NAMES[dow].lower(),
            "schedule_is_today": day == today,
            "day_working": [{"name": name_of[i], "shift_slot": " y ".join(d[dow])}
                            for i, d in custom_days.items() if dow in d],
            "day_off": [name_of[i] for i, d in custom_days.items() if dow not in d],
        }
    logger.info(
        "afrodita_staff_schedule company_id=%s week=%s day=%s employees=%s custom=%s default=%s ambiguous=%s "
        "without=%s", cid, week, day, len(employees), len(roster), len(default_only), len(ambiguous), len(without),
    )
    return result


def _undecided_text(data: Dict[str, Any]) -> str:
    """Frases de los empleados sin turno decidido (horario base, ambiguos, sin horario) + la peticion."""
    out = ""
    default_only = list(data.get("default_schedule_only") or [])
    ambiguous = list(data.get("ambiguous_schedule") or [])
    without = list(data.get("without_schedule") or [])
    if default_only:
        quien = "solo tiene" if len(default_only) == 1 else "solo tienen"
        alta = "darlo" if len(default_only) == 1 else "darlos"
        out += (f" {_y_join(default_only)}: {quien} el horario base que pone el sistema al {alta} de alta "
                f"({DEFAULT_SCHEDULE_LABEL}); si no es su horario real, dime sus turnos.")
    if ambiguous:
        tiene = "tiene" if len(ambiguous) == 1 else "tienen"
        out += (f" {_y_join(ambiguous)}: {tiene} horarios guardados en varias de tus empresas y no puedo saber "
                "cuál es de esta; dime su turno aquí.")
    if without:
        out += (f" Sin horario: {_y_join(without)}. Dime sus turnos (qué días y de qué hora a qué hora) "
                "para completar el cuadrante.")
    return out


def _staff_member_text(data: Dict[str, Any]) -> str:
    """Respuesta de la consulta de UN empleado: solo sus datos (turnos reales, sin horario, horario base o
    ambiguo). Si hay varios con ese nombre, se dan todos."""
    q = str(data.get("employee_query") or "").strip()
    total = int(data.get("employees_total") or 0)
    if not total:
        return f"No encuentro a «{q}» entre los empleados activos de tu empresa."
    dv = data.get("schedule_day") or {}
    day_slot = {w["name"]: w["shift_slot"] for w in dv.get("day_working") or []}
    when = ""
    if dv:
        when = f"hoy ({dv['schedule_day_name']})" if dv.get("schedule_is_today") else f"el {dv['schedule_day_name']}"
    parts: List[str] = []
    for r in data.get("roster") or []:
        who = f"{r['name']} ({r['role_title']})" if r.get("role_title") else r["name"]
        if dv:
            slot = day_slot.get(r["name"])
            parts.append(f"Según los turnos guardados, {who} {when} trabaja {slot}." if slot
                         else f"Según los turnos guardados, {who} {when} libra.")
        else:
            parts.append(f"Turnos guardados de {who}: {r['shift_week']}.")
    for n in data.get("default_schedule_only") or []:
        parts.append(f"{n}: solo tiene el horario base que pone el sistema en el alta ({DEFAULT_SCHEDULE_LABEL}); "
                     "si no es su horario real, dime su turno.")
    for n in data.get("ambiguous_schedule") or []:
        parts.append(f"{n}: tiene horarios guardados en varias de tus empresas y no puedo saber cuál es de esta; "
                     "dime su turno aquí.")
    for n in data.get("without_schedule") or []:
        parts.append(f"{n}: no tiene horario guardado; dime su turno (qué días y de qué hora a qué hora). "
                     "Para que quede guardado, añádelo en Control horario.")
    head = f"Hay {total} empleados con ese nombre en tu empresa. " if total > 1 else ""
    return (head + " ".join(parts)).strip()


def staff_schedule_text(data: Dict[str, Any]) -> str:
    """Respuesta del chat con el cuadrante real; si falta el dato, lo pide (nunca inventa horarios)."""
    if data.get("employee_query") is not None:
        return _staff_member_text(data)
    total = int(data.get("employees_total") or 0)
    if not total:
        return ("No hay empleados dados de alta en tu empresa, así que no puedo montar el cuadrante. "
                "Añádelos en Control horario (nombre y puesto) y luego dime los turnos.")
    roster = list(data.get("roster") or [])
    default_only = list(data.get("default_schedule_only") or [])
    ambiguous = list(data.get("ambiguous_schedule") or [])
    without = list(data.get("without_schedule") or [])
    ask = (f"Dime el horario de apertura y los turnos (por ejemplo, mañana de 09:00 a 16:00 y tarde de 16:00 "
           f"a 23:00) y qué días trabaja{' cada uno' if total > 1 else ''}, y te propongo el reparto. Para que "
           "quede guardado, "
           "añade los horarios en Control horario.")
    if not roster:
        everyone = _y_join([n for n in default_only + ambiguous + without])
        one = total == 1
        if default_only and len(default_only) == total:
            return (f"Tengo a {everyone} en tu empresa, pero {'solo tiene' if one else 'solo tienen'} el horario "
                    f"base que pone el sistema al {'darlo' if one else 'darlos'} de alta ({DEFAULT_SCHEDULE_LABEL}), "
                    f"no {'un turno decidido' if one else 'turnos decididos'}, así que no te monto el cuadrante "
                    f"con eso. {ask}")
        if without and len(without) == total:
            quien = "no tiene" if one else "ninguno tiene"
            return (f"Tengo a {everyone} en tu empresa, pero {quien} horario guardado, así que no te monto el "
                    f"cuadrante inventándomelo. {ask}")
        return (f"Tengo a {everyone} en tu empresa, pero {'no tiene' if one else 'ninguno tiene'} un turno "
                f"decidido que pueda darte por bueno, así que no te monto el cuadrante inventándomelo."
                f"{_undecided_text(data)}").strip()

    dv = data.get("schedule_day")
    if dv:
        name = dv["schedule_day_name"]
        when = f"hoy ({name})" if dv.get("schedule_is_today") else f"el {name}"
        work = dv.get("day_working") or []
        off = dv.get("day_off") or []
        if work:
            out = (f"Según los turnos guardados, {when} {'trabaja' if len(work) == 1 else 'trabajan'}: "
                   + "; ".join(f"{w['name']} {w['shift_slot']}" for w in work) + ".")
        else:
            out = f"Según los turnos guardados, {when} no trabaja nadie."
        if off:
            out += f" Libra{'n' if len(off) > 1 else ''}: {_y_join(off)}."
        return out + _undecided_text(data)

    when = "de la semana que viene" if data.get("schedule_week") == "next" else "semanal"
    head = (f"Cuadrante {when} con los horarios guardados ({total} "
            f"{'empleado' if total == 1 else 'empleados'}, {len(roster)} con turno decidido): ")
    lines = []
    for r in roster:
        who = f"{r['name']} ({r['role_title']})" if r.get("role_title") else r["name"]
        lines.append(f"{who}: {r['shift_week']}")
    out = head + ". ".join(lines) + "."
    gaps = data.get("uncovered_days") or []
    if gaps:
        out += f" Sin nadie asignado: {_y_join(gaps)}."
    return out + _undecided_text(data)


def execute_face_checkin(db: Session, user: User, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Deshabilitado en afrodita_finalization_v1 — sin motor biométrico."""
    _ = db, user, payload
    return {
        "disabled": True,
        "dry_run": True,
        "reason": "no_biometric_engine",
        "ui_method": "face",
        "message": "Fichaje facial deshabilitado. Use fichaje QR en dominio RRHH.",
        "redirect": "/api/v1/afrodita/rrhh/v1/checkin/qr",
    }


def execute_qr_checkin(db: Session, user: User, code: str) -> Dict[str, Any]:
    """Fichaje QR real vía scan_flow → register_checkin cuando flags lo permiten."""
    from services.scan_flow_service_v1 import process_nfc_scan, process_qr_scan

    validation = validate_qr_before_checkin(db, user, code)

    if not can_execute_checkin():
        from services.afrodita_unified_control import assert_can_write

        assert_can_write(db)

    log_execution_attempt(
        domain="rrhh",
        action="register_checkin",
        allowed=True,
        actor_id=user.id,
    )

    if code.upper().startswith(("ZEUS|", "ZEUSQR|")):
        flow = process_qr_scan(db, user, data=code)
    else:
        flow = process_nfc_scan(db, user, text=code, checkin_type="entrada")

    session = flow.get("session") if isinstance(flow.get("session"), dict) else {}
    checkin_id = flow.get("checkin_id") or session.get("checkin_id")
    persisted = bool(flow.get("executed", flow.get("success"))) and bool(checkin_id)

    if not persisted:
        raise HTTPException(
            status_code=500,
            detail="Fichaje no persistido en time_cost_checkins pese a ejecución habilitada",
        )

    return {
        **flow,
        "checkin_id": int(checkin_id),
        "status": "executed",
        "validation": validation,
        "entry_point": "register_checkin",
        "message": flow.get("message") or f"Fichaje registrado (checkin_id={checkin_id}).",
    }


def validate_qr_before_checkin(db: Session, user: User, code: str) -> Dict[str, Any]:
    """Pre-validación QR: frescura + empleado en BD."""
    from services.afrodita_unified_control import parse_zeuscheck_code

    flags = current_flags()
    fresh_ok, fresh_reason = validate_qr_freshness(code)
    info: Dict[str, Any] = {"freshness_ok": fresh_ok, "freshness_reason": fresh_reason}

    zeus = parse_zeuscheck_code(code)
    if zeus and zeus.get("employee_id"):
        cid = primary_company_id_for_user(db, user)
        info["employee_id"] = zeus["employee_id"]
        info["employee_exists"] = bool(
            cid and employee_exists(db, company_id=cid, employee_code=str(zeus["employee_id"]))
        )
    else:
        info["employee_exists"] = None

    if flags["AFRODITA_USE_REAL_CHECKINS"] and zeus:
        if not fresh_ok:
            raise HTTPException(
                status_code=422,
                detail=f"QR ZEUSCHECK inválido: {fresh_reason} (máx 5 min)",
            )
        if info.get("employee_exists") is False:
            raise HTTPException(
                status_code=404,
                detail=f"Empleado {zeus.get('employee_id')} no existe en company_employees",
            )

    info["execution_allowed"] = can_execute_checkin()
    return info
