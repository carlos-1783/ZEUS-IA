"""CLIENT_EXCEL_IMPORT_PIPELINE_V2 — real execution (parse → validate → bulk upsert → events → audit)."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd  # pyright: ignore[reportMissingImports]
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.user import User
from app.schemas.crm_import import CrmImportColumnMapping
import services.crm_import_service as crm_import_svc
import services.crm_office_service as crm_svc

logger = logging.getLogger(__name__)

PIPELINE_NAME = "CLIENT_EXCEL_IMPORT_PIPELINE_V2"
PHONE_RE = re.compile(r"^\+?[0-9]{9,15}$")

_parse_importe = crm_import_svc._parse_importe


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_file_rows(
    file_id: str,
    user_id: int,
    *,
    trim: bool = True,
) -> Tuple[List[Dict[str, Any]], str]:
    """Step parse_csv / parse_file — normalized row dicts from stored upload."""
    df, filename = crm_import_svc._read_dataframe(file_id, user_id)
    rows: List[Dict[str, Any]] = []
    for _, series in df.iterrows():
        row = {str(k): (str(v).strip() if trim and v is not None else v) for k, v in series.items()}
        rows.append(row)
    return rows, filename


def validate_clients(
    raw_rows: List[Dict[str, Any]],
    mapping: CrmImportColumnMapping,
    *,
    on_error: str = "skip_row",
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Step validate_clients — required nombre+telefono, phone format, numeric importe."""
    clients: List[Dict[str, Any]] = []
    errors: List[str] = []

    name_col = mapping.name
    phone_col = mapping.phone
    if not name_col or not phone_col:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El pipeline V2 requiere columnas de nombre y teléfono en el mapeo.",
        )

    importe_col = getattr(mapping, "importe", None)

    for idx, row in enumerate(raw_rows):
        row_num = idx + 2
        nombre = (row.get(name_col) or "").strip() if name_col in row else ""
        telefono_raw = (row.get(phone_col) or "").strip() if phone_col in row else ""
        telefono = crm_import_svc._norm_phone(telefono_raw)

        if not nombre or not telefono:
            if on_error == "skip_row":
                continue
            errors.append(f"Fila {row_num}: faltan nombre o teléfono.")
            continue

        if not PHONE_RE.match(telefono):
            if on_error == "skip_row":
                if len(errors) < 20:
                    errors.append(f"Fila {row_num}: teléfono inválido.")
                continue
            errors.append(f"Fila {row_num}: teléfono inválido.")
            continue

        importe: Optional[float] = None
        if importe_col and importe_col in row:
            importe = _parse_importe(row.get(importe_col))
            if row.get(importe_col) and importe is None:
                if on_error == "skip_row":
                    if len(errors) < 20:
                        errors.append(f"Fila {row_num}: importe no numérico.")
                    continue
                errors.append(f"Fila {row_num}: importe no numérico.")
                continue

        email = None
        if mapping.email and mapping.email in row:
            email = crm_import_svc._validate_email(row.get(mapping.email))

        notes = None
        if mapping.notes and mapping.notes in row:
            notes = (row.get(mapping.notes) or "").strip() or None

        tax_id = None
        if mapping.tax_id and mapping.tax_id in row:
            tax_id = re.sub(r"\s+", "", str(row.get(mapping.tax_id) or ""))[:50] or None

        clients.append(
            {
                "nombre": nombre[:100],
                "telefono": telefono[:20],
                "email": email,
                "notes": notes,
                "tax_id": tax_id,
                "importe": importe,
            }
        )

    return clients, errors


def _find_existing(
    db: Session,
    company_id: int,
    *,
    email: Optional[str],
    telefono: Optional[str],
) -> Optional[Customer]:
    q = db.query(Customer).filter(Customer.company_id == company_id)
    if email:
        found = q.filter(Customer.email == email).first()
        if found:
            return found
    if telefono:
        found = q.filter(Customer.phone == telefono).first()
        if found:
            return found
    return None


def bulk_create_clients(
    db: Session,
    user: User,
    clients: List[Dict[str, Any]],
    *,
    company_id: int,
    deduplicate_by: Optional[List[str]] = None,
    upsert: bool = True,
) -> Tuple[List[Customer], int, int]:
    """Step create_clients (AFRODITA) — insert or update by telefono/email."""
    dedupe_keys = deduplicate_by or ["telefono", "email"]
    created: List[Customer] = []
    inserted = 0
    updated = 0
    seen_emails: Set[str] = set()
    seen_phones: Set[str] = set()

    for item in clients:
        email = (item.get("email") or "").strip().lower() or None
        telefono = item.get("telefono")
        if "email" in dedupe_keys and email and email in seen_emails:
            continue
        if "telefono" in dedupe_keys and telefono and telefono in seen_phones:
            continue

        meta = {"importe": item["importe"]} if item.get("importe") is not None else {}
        if item.get("importe"):
            meta["pending_amount"] = item["importe"]

        existing = _find_existing(db, company_id, email=email, telefono=telefono)
        if existing:
            if not upsert:
                continue
            existing.name = item["nombre"]
            if email:
                existing.email = email
            if telefono:
                existing.phone = telefono
            if item.get("notes"):
                existing.notes = item["notes"]
            if item.get("tax_id"):
                existing.tax_id = item["tax_id"]
            prev_meta = existing.metadata_ if isinstance(existing.metadata_, dict) else {}
            existing.metadata_ = {**prev_meta, **meta}
            db.flush()
            created.append(existing)
            updated += 1
        else:
            customer = Customer(
                name=item["nombre"],
                email=email,
                phone=telefono,
                tax_id=item.get("tax_id"),
                notes=item.get("notes"),
                is_active=True,
                is_company=True,
                company_id=company_id,
                owner_user_id=user.id,
                metadata_=meta or None,
            )
            db.add(customer)
            db.flush()
            created.append(customer)
            inserted += 1

        if email:
            seen_emails.add(email)
        if telefono:
            seen_phones.add(telefono)

    return created, inserted, updated


def _emit_payment_due(
    db: Session,
    user: User,
    *,
    client_id: int,
    nombre: str,
    importe: float,
    source: str = "excel_import",
    trace_id: str,
) -> Dict[str, Any]:
    from services.zeus_event_bus_v1 import emit_event

    payload = {
        "client_id": client_id,
        "customer_id": client_id,
        "name": nombre,
        "nombre": nombre,
        "amount": importe,
        "importe": importe,
        "status": "pending",
        "source": source,
        "trace_id": trace_id,
        "pipeline": PIPELINE_NAME,
    }
    return emit_event(
        db,
        user,
        event_name="payment_due",
        source_module="AFRODITA",
        payload=payload,
    )


def emit_events_per_client(
    db: Session,
    user: User,
    created_clients: List[Customer],
    *,
    trace_id: str,
) -> Dict[str, int]:
    """Step emit_events_per_client — client_created + payment_due when importe > 0."""
    from services.zeus_crm_hooks_v1 import on_client_created

    counts = {"client_created": 0, "payment_due": 0}
    for customer in created_clients:
        try:
            on_client_created(db, user, customer)
            counts["client_created"] += 1
        except Exception as exc:
            logger.warning("[IMPORT_V2] client_created failed id=%s: %s", customer.id, exc)

        meta = customer.metadata_ if isinstance(customer.metadata_, dict) else {}
        importe = meta.get("importe") or meta.get("pending_amount")
        try:
            amount = float(importe) if importe is not None else 0.0
        except (TypeError, ValueError):
            amount = 0.0

        if amount > 0:
            try:
                _emit_payment_due(
                    db,
                    user,
                    client_id=customer.id,
                    nombre=customer.name,
                    importe=amount,
                    trace_id=trace_id,
                )
                counts["payment_due"] += 1
            except Exception as exc:
                logger.warning("[IMPORT_V2] payment_due failed id=%s: %s", customer.id, exc)

    return counts


def maybe_force_high_risk_demo(
    db: Session,
    user: User,
    created_clients: List[Customer],
    *,
    trace_id: str,
) -> bool:
    """Step force_high_risk_demo — extra payment_due when any importe > 1000."""
    has_high = False
    for customer in created_clients:
        meta = customer.metadata_ if isinstance(customer.metadata_, dict) else {}
        try:
            amount = float(meta.get("importe") or meta.get("pending_amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount > 1000:
            has_high = True
            break

    if not has_high:
        return False

    anchor = created_clients[0]
    _emit_payment_due(
        db,
        user,
        client_id=anchor.id,
        nombre=anchor.name,
        importe=1500.0,
        source="demo_boost",
        trace_id=trace_id,
    )
    return True


def audit_import_completed(
    db: Session,
    user: User,
    *,
    trace_id: str,
    clients_processed: int,
    output: Dict[str, Any],
) -> Optional[str]:
    from services.zeus_automation_audit_v1 import record_automation_audit

    return record_automation_audit(
        db,
        automation_name="excel_import_completed",
        agent="AFRODITA",
        trigger_type="file_upload",
        status="success",
        input_data={
            "type": "excel_import_completed",
            "pipeline": PIPELINE_NAME,
            "source": "excel_import",
            "trace_id": trace_id,
        },
        output_data={
            "clients_processed": clients_processed,
            "trace_id": trace_id,
            **output,
        },
        user_id=user.id,
    )


def run_client_excel_import_pipeline_v2(
    db: Session,
    user: User,
    *,
    file_id: str,
    mapping: CrmImportColumnMapping,
    source: str = "admin_clients_import",
) -> Dict[str, Any]:
    """Execute full CLIENT_EXCEL_IMPORT_PIPELINE_V2 on a stored upload."""
    trace_id = uuid.uuid4().hex
    company_id = crm_svc.primary_company_id(db, user)
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere una empresa asociada para importar clientes.",
        )

    raw_rows, filename = parse_file_rows(file_id, user.id)
    clients, validation_errors = validate_clients(raw_rows, mapping, on_error="skip_row")

    if not clients:
        crm_import_svc.delete_upload(file_id)
        return {
            "success": True,
            "pipeline": PIPELINE_NAME,
            "trace_id": trace_id,
            "imported": 0,
            "updated": 0,
            "skipped": len(raw_rows),
            "skipped_empty": 0,
            "skipped_duplicates": 0,
            "skipped_invalid": len(raw_rows) - len(clients),
            "errors": validation_errors,
            "events_emitted": {"client_created": 0, "payment_due": 0},
            "demo_boost_emitted": False,
            "message": "No se importó ningún cliente (filas inválidas o sin teléfono).",
        }

    try:
        created_clients, inserted, updated = bulk_create_clients(
            db,
            user,
            clients,
            company_id=company_id,
            deduplicate_by=["telefono", "email"],
            upsert=True,
        )

        event_counts = emit_events_per_client(db, user, created_clients, trace_id=trace_id)
        demo_boost = maybe_force_high_risk_demo(db, user, created_clients, trace_id=trace_id)

        crm_svc.log_activity(
            db,
            company_id=company_id,
            user_id=user.id,
            customer_id=None,
            record_id=None,
            action="customers_imported",
            summary=f"Pipeline V2: {inserted} nuevo(s), {updated} actualizado(s) desde {filename}",
            payload={
                "pipeline": PIPELINE_NAME,
                "trace_id": trace_id,
                "source": source,
                "filename": filename,
                "imported": inserted,
                "updated": updated,
                "events": event_counts,
            },
            commit=False,
        )

        audit_id = audit_import_completed(
            db,
            user,
            trace_id=trace_id,
            clients_processed=len(clients),
            output={
                "imported": inserted,
                "updated": updated,
                "events_emitted": event_counts,
                "demo_boost_emitted": demo_boost,
                "filename": filename,
            },
        )

        db.commit()
        logger.info(
            "[IMPORT_V2] ok user=%s trace=%s inserted=%s updated=%s events=%s",
            user.id,
            trace_id,
            inserted,
            updated,
            event_counts,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("[IMPORT_V2] failed file_id=%s trace=%s", file_id, trace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en pipeline de importación: {exc}",
        ) from exc
    finally:
        crm_import_svc.delete_upload(file_id)

    skipped = len(raw_rows) - len(clients)
    total_saved = inserted + updated
    return {
        "success": True,
        "pipeline": PIPELINE_NAME,
        "trace_id": trace_id,
        "audit_id": audit_id,
        "imported": total_saved,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "skipped_empty": 0,
        "skipped_duplicates": 0,
        "skipped_invalid": skipped,
        "errors": validation_errors,
        "events_emitted": event_counts,
        "demo_boost_emitted": demo_boost,
        "message": (
            f"Pipeline V2: {inserted} cliente(s) nuevos, {updated} actualizado(s). "
            f"Eventos: {event_counts['client_created']} client_created, "
            f"{event_counts['payment_due']} payment_due."
        ),
    }
