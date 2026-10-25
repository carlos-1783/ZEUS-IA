"""Numeracion de facturas de la serie INV (INV-YYYYMMDD-N), segura ante concurrencia y SIN migracion.

Estado real (verificado en alembic 0001 y app/models/erp.py):
- `invoices.invoice_number` tiene un indice UNIQUE GLOBAL (ix_invoices_invoice_number), no por empresa.
- El numero de la serie INV es GLOBAL: N era `count(*) de TODAS las facturas + 1` (todas las empresas y
  todas las series, incluidas las FRA-<ticket> del TPV). La fecha solo es prefijo; N no reinicia por dia.
- Series existentes: INV-YYYYMMDD-N (POST /invoices/ y escaneo QR) y FRA-<ticket_id> (TPV, derivado del
  ticket, unico por venta; no pasa por aqui).

Problemas de count+1:
1. Dos creaciones simultaneas leen el mismo count y generan el mismo numero -> la segunda choca con el
   UNIQUE -> IntegrityError -> 500.
2. Con RLS activo (rol sin BYPASSRLS, tabla invoices con FORCE ROW LEVEL SECURITY y get_db_scoped) el
   count solo ve las facturas de la propia empresa: dos empresas generan el mismo INV-...-N el mismo dia
   y la segunda da 500 aunque no haya concurrencia.
3. Si alguna factura se borra, count+1 repite un numero ya usado.

Solucion sin tocar el esquema:
- Bloqueo transaccional GLOBAL (el numero es global): `pg_advisory_xact_lock(<clave fija>)` dentro de la
  transaccion de creacion. Se libera solo en commit/rollback; serializa unicamente la asignacion+insercion
  de facturas INV.
- N = (mayor sufijo numerico existente de la serie INV) + 1, leido DESPUES de obtener el bloqueo (en READ
  COMMITTED cada sentencia ve lo ya confirmado por la transaccion que solto el bloqueo). Nunca choca con
  un numero existente aunque haya huecos o filas borradas (count+1 si chocaba). El formato no cambia.
  (Hoy no hay endpoint que borre facturas; si se borrara la de N maximo, ese N se reutilizaria.)
- Esa lectura se hace sin el filtro de empresa de RLS (se vacia app.current_company_id SOLO para esa
  sentencia y se restaura): el UNIQUE es global, asi que hay que ver los numeros de todas las empresas.
  La sentencia solo devuelve invoice_number de la serie INV; no se expone nada al cliente salvo el numero
  nuevo (que ya era global antes de este cambio). Esto DEPENDE de que la policy de invoices sea
  fail-open con contexto vacio (0047_row_level_security.py:68-80); si se endurece a fail-closed hay que
  pasar a una funcion SECURITY DEFINER (migracion) o volverian los choques del UNIQUE.
- En SQLite (tests) no hay advisory locks ni RLS: se omiten y el calculo es el mismo.

PENDIENTE (requiere migracion, NO incluida): numeracion correlativa POR EMPRESA y serie (lo que pide la
normativa de facturacion) necesita sustituir el UNIQUE global por UNIQUE(company_id, invoice_number) y una
tabla de contadores (company_id, serie, ultimo_numero) actualizada con UPDATE ... RETURNING.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

INVOICE_SERIES = "INV"
_PREFIX_LEN = len(INVOICE_SERIES) + 1 + 8 + 1  # "INV-" + YYYYMMDD + "-"
_NUMBER_RE = re.compile(r"^INV-\d{8}-([1-9]\d*)$")
# Clave fija (bigint con signo) del advisory lock de la serie INV: global, igual en todos los procesos.
INVOICE_NUMBER_LOCK_KEY = int.from_bytes(
    hashlib.sha256(b"zeus:invoice_number:INV").digest()[:8], "big", signed=True
)
_PAGE = 200


def _is_postgres(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def _max_series_suffix(db: Session) -> int:
    """Mayor N de los numeros con forma INV-YYYYMMDD-N (0 si no hay ninguno).

    Orden portable (Postgres y SQLite): por longitud del sufijo y despues el sufijo como texto; para
    sufijos de solo digitos sin ceros a la izquierda eso es orden numerico. Las filas de la serie que no
    tengan exactamente esa forma (legacy, sufijo no numerico) se saltan."""
    offset = 0
    while True:
        rows = db.execute(
            text(
                "SELECT invoice_number FROM invoices WHERE invoice_number LIKE 'INV-%' "
                "ORDER BY length(invoice_number) DESC, substr(invoice_number, :p) DESC "
                "LIMIT :lim OFFSET :off"
            ),
            {"p": _PREFIX_LEN + 1, "lim": _PAGE, "off": offset},
        ).scalars().all()
        for number in rows:
            m = _NUMBER_RE.match(number or "")
            if m:
                return int(m.group(1))
        if len(rows) < _PAGE:
            return 0
        offset += _PAGE


def _acquire_series_lock(db: Session) -> None:
    """Bloqueo transaccional GLOBAL de la serie INV (solo Postgres). Se libera en commit/rollback."""
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": INVOICE_NUMBER_LOCK_KEY})


def next_invoice_number(db: Session, *, now: Optional[datetime] = None) -> str:
    """Reserva el siguiente numero INV-YYYYMMDD-N dentro de la transaccion actual de `db`.

    Debe llamarse en la MISMA transaccion que inserta la factura, justo antes de insertarla: en Postgres
    el bloqueo se mantiene hasta su commit/rollback, asi que nadie puede leer el mismo maximo entretanto."""
    pg = _is_postgres(db)
    if pg:
        _acquire_series_lock(db)
        # DEPENDE DEL RLS "FAIL-OPEN": la lectura global funciona porque la policy de invoices
        # (alembic/versions/0047_row_level_security.py:68-80, tenant_isolation_invoices) deja ver TODAS
        # las filas cuando app.current_company_id esta vacio. Si algun dia esa policy se endurece a
        # fail-closed, este helper debe pasar a una funcion SECURITY DEFINER (requiere migracion): si no,
        # el maximo saldria 0 (o solo el de la propia empresa) y volverian los choques con el UNIQUE.
        prev_company = db.execute(text("SELECT current_setting('app.current_company_id', true)")).scalar()
        db.execute(text("SELECT set_config('app.current_company_id', '', true)"))
    try:
        last = _max_series_suffix(db)
        if pg:
            db.execute(text("SELECT set_config('app.current_company_id', :v, true)"), {"v": prev_company or ""})
    except Exception:
        # La transaccion no debe seguir con el contexto de empresa vaciado (ni, en Postgres, quedar
        # abortada a medias): se descarta entera y el error sube al llamador.
        db.rollback()
        logger.exception("invoice_numbering: no se pudo calcular el siguiente numero de la serie %s", INVOICE_SERIES)
        raise
    number = f"{INVOICE_SERIES}-{(now or datetime.utcnow()).strftime('%Y%m%d')}-{last + 1}"
    logger.info("invoice_numbering: asignado %s (anterior N=%s, bloqueo=%s)", number, last, "pg_advisory_xact" if pg else "no")
    return number
