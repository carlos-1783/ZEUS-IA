"""Numeracion de facturas de la serie INV (INV-YYYYMMDD-N): correlativa POR EMPRESA, con contador en BD.

Estado (migracion 0070_invoice_numbering_per_company):
- `invoices.invoice_number` es unico POR EMPRESA (uq_invoices_company_id_invoice_number), ya no global.
- `invoice_counters(company_id, series, last_number)` guarda el ultimo N emitido de cada empresa y serie,
  inicializado al mayor N que cada empresa ya tenia (sin renumerar nada emitido).
- Series: INV-YYYYMMDD-N (POST /invoices/ y escaneo QR, pasan por aqui) y FRA-<ticket_id> (TPV, derivado del
  ticket, unico por venta; no usa contador).

Como se asigna N (PostgreSQL): `SELECT invoice_next_number(company_id, 'INV')`, funcion de la migracion 0070,
que hace `UPDATE invoice_counters SET last_number = last_number + 1 ... RETURNING` (o el INSERT inicial con
ON CONFLICT) en la MISMA transaccion que inserta la factura:
- Concurrencia: el UPDATE bloquea la fila del contador hasta commit/rollback; otra alta de la misma empresa
  espera y recibe N+1. Empresas distintas no se bloquean entre si. No se cuentan filas ni se lee el maximo.
- Sin huecos: si la creacion hace rollback, el UPDATE del contador se deshace con ella y el numero no se
  consume (una SEQUENCE no serviria: nextval no se deshace con rollback).
- Sin lectura entre empresas: la funcion es SECURITY INVOKER y solo toca la fila de la propia empresa; con la
  RLS endurecida (fail-closed) sigue funcionando con el contexto de empresa de la peticion.
La fecha del numero es solo prefijo informativo: N no reinicia por dia.

En SQLite (tests) no hay funciones plpgsql: se hace el mismo UPDATE/INSERT sobre invoice_counters desde Python
(SQLite serializa las escrituras de toda la BD, asi que no hay carrera que proteger).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

INVOICE_SERIES = "INV"
_PG_UNDEFINED_FUNCTION = "42883"
NUMBERING_UNAVAILABLE_DETAIL = {
    "error": "invoice_numbering_unavailable",
    "message": "La numeración de facturas no está disponible: falta la migración 0070 "
               "(función invoice_next_number) en la base de datos. No se ha creado la factura.",
}


def _is_postgres(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def _next_counter_value_pg(db: Session, company_id: int, series: str) -> int:
    """UPDATE ... RETURNING del contador via la funcion SQL de la migracion 0070 (bloquea la fila hasta el
    commit/rollback de la transaccion de `db`)."""
    try:
        return int(db.execute(
            text("SELECT invoice_next_number(:c, :s)"), {"c": company_id, "s": series}
        ).scalar_one())
    except DBAPIError as exc:
        if getattr(exc.orig, "pgcode", None) == _PG_UNDEFINED_FUNCTION:
            # BD sin la migracion 0070 (el arranque ya se detiene si el upgrade falla, pero puede pasar con
            # SKIP_DB_MIGRATE=1 o una BD restaurada de antes de 0070): error claro (503) en vez de un 500
            # opaco. El llamador hace rollback y lo registra.
            logger.error("invoice_numbering: falta la funcion invoice_next_number (migracion 0070 no aplicada)")
            raise HTTPException(status_code=503, detail=NUMBERING_UNAVAILABLE_DETAIL) from exc
        raise


def _next_counter_value_portable(db: Session, company_id: int, series: str) -> int:
    """Mismo contrato que la funcion SQL invoice_next_number, para motores sin plpgsql (SQLite)."""
    updated = db.execute(
        text("UPDATE invoice_counters SET last_number = last_number + 1, updated_at = CURRENT_TIMESTAMP "
             "WHERE company_id = :c AND series = :s"),
        {"c": company_id, "s": series},
    ).rowcount
    if not updated:
        db.execute(
            text("INSERT INTO invoice_counters (company_id, series, last_number, updated_at) "
                 "VALUES (:c, :s, 1, CURRENT_TIMESTAMP)"),
            {"c": company_id, "s": series},
        )
    return int(db.execute(
        text("SELECT last_number FROM invoice_counters WHERE company_id = :c AND series = :s"),
        {"c": company_id, "s": series},
    ).scalar_one())


def next_invoice_number(db: Session, company_id: int, *, now: Optional[datetime] = None) -> str:
    """Reserva el siguiente numero INV-YYYYMMDD-N de `company_id` dentro de la transaccion actual de `db`.

    Debe llamarse en la MISMA transaccion que inserta la factura: el contador queda bloqueado (Postgres) hasta
    su commit/rollback, y si esa transaccion se deshace el numero vuelve a quedar libre."""
    if company_id is None:
        raise ValueError("next_invoice_number: company_id es obligatorio (la serie es por empresa)")
    company_id = int(company_id)
    try:
        if _is_postgres(db):
            n = _next_counter_value_pg(db, company_id, INVOICE_SERIES)
        else:
            n = _next_counter_value_portable(db, company_id, INVOICE_SERIES)
    except Exception:
        # La transaccion no debe seguir a medias (en Postgres quedaria abortada): se descarta entera.
        db.rollback()
        logger.exception("invoice_numbering: no se pudo reservar numero serie=%s company_id=%s",
                         INVOICE_SERIES, company_id)
        raise
    number = f"{INVOICE_SERIES}-{(now or datetime.utcnow()).strftime('%Y%m%d')}-{n}"
    logger.info("invoice_numbering: asignado %s company_id=%s", number, company_id)
    return number
