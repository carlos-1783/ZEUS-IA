"""Dia natural de la empresa (hora peninsular) -> limites en UTC para filtrar la BD.

"Ayer" y "hoy" para un negocio espanol son dias de Europe/Madrid, no de UTC: una venta a las
00:30 hora local es del dia nuevo aunque en UTC aun sea el anterior. Si el sistema no tiene la
base de datos de zonas horarias se usa UTC y se indica en la salida (`timezone`).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Optional, Tuple

LOCAL_TZ_NAME = "Europe/Madrid"


def local_tz() -> Tuple[tzinfo, str]:
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(LOCAL_TZ_NAME), LOCAL_TZ_NAME
    except Exception:  # sin tzdata en el sistema: se declara UTC, no se finge hora local
        return timezone.utc, "UTC"


def today_local(now: Optional[datetime] = None) -> date:
    tz, _ = local_tz()
    return (now or datetime.now(timezone.utc)).astimezone(tz).date()


def resolve_day(value: Optional[str], now: Optional[datetime] = None) -> date:
    """None/"yesterday" -> ayer; "today" -> hoy; "YYYY-MM-DD" -> esa fecha (no futura).
    Cualquier otro valor -> ValueError (nunca se adivina)."""
    today = today_local(now)
    v = (value or "yesterday").strip().lower()
    if v == "yesterday":
        return today - timedelta(days=1)
    if v == "today":
        return today
    d = date.fromisoformat(v)
    if d > today:
        raise ValueError("fecha futura")
    return d


def day_bounds_utc(day: date) -> Tuple[datetime, datetime]:
    """[inicio, fin) del dia local, en UTC (aware)."""
    tz, _ = local_tz()
    start = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
    return start, end


def local_days_range_utc_naive(
    first_day: Optional[date], last_day: Optional[date]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Rango [inicio del dia local `first_day`, inicio del dia local siguiente a `last_day`) en UTC
    SIN zona, para comparar con columnas DateTime naive UTC (p. ej. Invoice.issue_date).

    Ambos dias van incluidos enteros: una factura de `last_day` a las 23:59 hora local entra. Un
    extremo None -> ese limite es None (sin cota por ese lado)."""
    start = day_bounds_utc(first_day)[0].replace(tzinfo=None) if first_day is not None else None
    end = day_bounds_utc(last_day)[1].replace(tzinfo=None) if last_day is not None else None
    return start, end
