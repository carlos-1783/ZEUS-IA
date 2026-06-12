"""
Compatibilidad BD legacy para motor fiscal RAFAEL (sin depender del ORM completo).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.db.base import engine

logger = logging.getLogger(__name__)


def table_column_names(table_name: str, schema: str = "public") -> set[str]:
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = :schema AND table_name = :table
                    """
                ),
                {"schema": schema, "table": table_name},
            ).fetchall()
        return {str(r[0]) for r in rows}
    except Exception as exc:
        logger.warning("table_column_names(%s): %s", table_name, exc)
        return set()


def table_exists(table_name: str, schema: str = "public") -> bool:
    return table_name in _table_names(schema)


def _table_names(schema: str = "public") -> set[str]:
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = :schema
                    """
                ),
                {"schema": schema},
            ).fetchall()
        return {str(r[0]) for r in rows}
    except Exception:
        return set()


def fiscal_schema_gaps() -> List[str]:
    gaps: List[str] = []
    if not table_exists("invoices"):
        gaps.append("tabla invoices")
        return gaps
    inv = table_column_names("invoices")
    if "company_id" not in inv:
        gaps.append("invoices.company_id")
    if "issue_date" not in inv:
        gaps.append("invoices.issue_date")
    if "subtotal" not in inv and "total" not in inv:
        gaps.append("invoices.subtotal/total")
    if not table_exists("expenses"):
        gaps.append("tabla expenses (opcional)")
    da = table_column_names("document_approvals")
    if not da:
        gaps.append("tabla document_approvals")
    else:
        for col in ("document_payload_json", "agent_name", "document_type"):
            if col not in da:
                gaps.append(f"document_approvals.{col}")
    return gaps


def fetch_invoice_totals_sql(
    db: Session,
    *,
    company_id: int,
    start: datetime,
    end: datetime,
) -> Tuple[float, float, int]:
    if not table_exists("invoices"):
        return 0.0, 0.0, 0

    cols = table_column_names("invoices")
    base_col = "subtotal" if "subtotal" in cols else ("total" if "total" in cols else None)
    tax_col = "tax_amount" if "tax_amount" in cols else None
    if not base_col:
        return 0.0, 0.0, 0

    date_col = "issue_date" if "issue_date" in cols else ("created_at" if "created_at" in cols else None)
    if not date_col:
        return 0.0, 0.0, 0

    tax_expr = f"COALESCE({tax_col}, 0)" if tax_col else "0"
    where = [f'"{date_col}" >= :start', f'"{date_col}" <= :end']
    params: Dict[str, Any] = {"start": start, "end": end, "cid": company_id}
    if "company_id" in cols:
        where.append('"company_id" = :cid')

    sql = text(
        f"""
        SELECT
          COALESCE(SUM(COALESCE("{base_col}", 0)), 0),
          COALESCE(SUM({tax_expr}), 0),
          COUNT(*)
        FROM invoices
        WHERE {" AND ".join(where)}
        """
    )
    row = db.execute(sql, params).one()
    return float(row[0] or 0), float(row[1] or 0), int(row[2] or 0)


def fetch_expense_totals_sql(
    db: Session,
    *,
    company_id: int,
    start: datetime,
    end: datetime,
) -> Tuple[float, int]:
    if not table_exists("expenses"):
        return 0.0, 0

    cols = table_column_names("expenses")
    if "tax_amount" not in cols or "issue_date" not in cols:
        return 0.0, 0

    where = ['"issue_date" >= :start', '"issue_date" <= :end']
    params: Dict[str, Any] = {"start": start, "end": end, "cid": company_id}
    if "company_id" in cols:
        where.append('"company_id" = :cid')

    sql = text(
        f"""
        SELECT COALESCE(SUM(COALESCE("tax_amount", 0)), 0), COUNT(*)
        FROM expenses
        WHERE {" AND ".join(where)}
        """
    )
    try:
        row = db.execute(sql, params).one()
        return float(row[0] or 0), int(row[1] or 0)
    except (OperationalError, ProgrammingError) as exc:
        db.rollback()
        logger.warning("fetch_expense_totals_sql: %s", exc)
        return 0.0, 0


def fetch_vat_breakdown_sql(
    db: Session,
    *,
    company_id: int,
    start: datetime,
    end: datetime,
) -> Dict[str, float]:
    if not table_exists("invoice_items") or not table_exists("invoices"):
        return {}

    inv_cols = table_column_names("invoices")
    item_cols = table_column_names("invoice_items")
    if "tax_rate" not in item_cols or "tax_amount" not in item_cols:
        return {}

    date_col = "issue_date" if "issue_date" in inv_cols else None
    if not date_col:
        return {}

    where = [f'i."{date_col}" >= :start', f'i."{date_col}" <= :end']
    params: Dict[str, Any] = {"start": start, "end": end, "cid": company_id}
    if "company_id" in inv_cols:
        where.append('i."company_id" = :cid')

    sql = text(
        f"""
        SELECT ii."tax_rate", COALESCE(SUM(COALESCE(ii."tax_amount", 0)), 0)
        FROM invoice_items ii
        JOIN invoices i ON i.id = ii.invoice_id
        WHERE {" AND ".join(where)}
        GROUP BY ii."tax_rate"
        """
    )
    try:
        rows = db.execute(sql, params).fetchall()
    except (OperationalError, ProgrammingError) as exc:
        db.rollback()
        logger.warning("fetch_vat_breakdown_sql: %s", exc)
        return {}

    breakdown: Dict[str, float] = {}
    for rate, amount in rows:
        r = round(float(rate or 0), 2)
        key = str(int(r)) if r == int(r) else str(r)
        breakdown[key] = breakdown.get(key, 0.0) + float(amount or 0)
    return breakdown


def insert_document_approval_row(
    db: Session,
    *,
    user_id: int,
    company_id: int,
    agent_name: str,
    document_type: str,
    payload: Dict[str, Any],
    status: str,
    fiscal_document_type: Optional[str],
    export_format: Optional[str],
    file_path: Optional[str],
    file_size: Optional[int],
    mime_type: Optional[str],
    audit_log: List[Dict[str, Any]],
    visible_in_workspace: bool = True,
) -> int:
    allowed = table_column_names("document_approvals")
    if not allowed:
        raise RuntimeError("Tabla document_approvals no existe en la base de datos.")

    row: Dict[str, Any] = {}
    candidates = {
        "user_id": user_id,
        "company_id": company_id,
        "agent_name": agent_name,
        "document_type": document_type,
        "document_payload_json": json.dumps(payload, ensure_ascii=False),
        "status": status,
        "visible_in_workspace": visible_in_workspace,
        "fiscal_document_type": fiscal_document_type,
        "export_format": export_format,
        "file_path": file_path,
        "file_size_bytes": file_size,
        "mime_type": mime_type,
        "audit_log_json": json.dumps(audit_log, ensure_ascii=False),
    }
    for key, value in candidates.items():
        if key in allowed:
            row[key] = value

    if "document_payload_json" not in row:
        raise RuntimeError("document_approvals sin columna document_payload_json.")

    col_names = ", ".join(f'"{k}"' for k in row)
    placeholders = ", ".join(f":{k}" for k in row)
    sql = text(f'INSERT INTO document_approvals ({col_names}) VALUES ({placeholders}) RETURNING id')

    try:
        doc_id = db.execute(sql, row).scalar()
        db.commit()
        if doc_id is None:
            raise RuntimeError("INSERT document_approvals no devolvió id.")
        return int(doc_id)
    except (OperationalError, ProgrammingError) as exc:
        db.rollback()
        raise RuntimeError(f"No se pudo guardar documento fiscal: {exc}") from exc
