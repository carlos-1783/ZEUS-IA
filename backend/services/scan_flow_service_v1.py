"""
zeus_full_real_flow_v3 — dispositivos físicos → validación → agentes → negocio → cashflow.
Sin mocks: toda acción persiste en BD y emite eventos.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.erp import Invoice, InvoiceItem, InvoiceStatus, InvoiceType
from app.models.scan_event import ScanEvent
from app.models.user import User
from app.schemas.customer import CustomerCreate
import services.crm_office_service as crm_svc
from services.event_bus import (
    emit_cashflow_updated,
    emit_invoice_generated,
    emit_scan_detected,
)
from services.mrz_parser_v1 import parse_mrz, parse_mrz_ocr
from services.time_cost_engine_v1 import register_checkin
from services.zeus_human_approval_v1 import request_approval, requires_approval
from services.zeus_scoring_engine_v1 import create_lead, score_customer, score_lead

logger = logging.getLogger(__name__)


def _company_id(db: Session, user: User, company_id: Optional[int]) -> int:
    cid = company_id or crm_svc.primary_company_id(db, user)
    if not cid:
        raise HTTPException(status_code=400, detail="company_id requerido.")
    return int(cid)


def _persist_scan(
    db: Session,
    *,
    company_id: int,
    user: User,
    scan_type: str,
    agent_name: str,
    raw_payload: str,
    parsed: Dict[str, Any],
    result: Dict[str, Any],
) -> ScanEvent:
    row = ScanEvent(
        company_id=company_id,
        user_id=user.id,
        scan_type=scan_type,
        agent_name=agent_name,
        raw_payload=raw_payload[:8000],
        parsed_json=json.dumps(parsed, ensure_ascii=False),
        result_json=json.dumps(result, ensure_ascii=False),
    )
    db.add(row)
    db.flush()
    return row


def _parse_qr_data(data: str) -> Dict[str, Any]:
    raw = (data or "").strip()
    if not raw:
        raise HTTPException(status_code=422, detail="QR vacío.")
    parts = raw.split("|")
    if parts[0].upper() in ("ZEUS", "ZEUSQR"):
        amount = 0.0
        if len(parts) > 2:
            try:
                amount = float(str(parts[2]).replace(",", "."))
            except ValueError:
                amount = 0.0
        return {
            "kind": "fiscal",
            "raw": raw,
            "customer_name": parts[1] if len(parts) > 1 else "",
            "amount": amount,
            "currency": parts[3] if len(parts) > 3 else "EUR",
            "email": parts[4] if len(parts) > 4 else None,
        }
    if parts[0].upper() == "ZEUSCHECK":
        return {
            "kind": "checkin",
            "raw": raw,
            "employee_id": parts[1] if len(parts) > 1 else None,
            "timestamp": parts[2] if len(parts) > 2 else None,
        }
    if parts[0].upper() == "CLIENT":
        return {
            "kind": "client_action",
            "raw": raw,
            "customer_ref": parts[1] if len(parts) > 1 else "",
            "action": (parts[2] if len(parts) > 2 else "VIEW").upper(),
        }
    return {"kind": "unknown", "raw": raw, "text": raw}


def _find_or_create_customer(
    db: Session,
    user: User,
    *,
    company_id: int,
    name: str,
    email: Optional[str] = None,
    tax_id: Optional[str] = None,
    phone: Optional[str] = None,
) -> Tuple[Customer, bool]:
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Nombre de cliente requerido.")

    q = db.query(Customer).filter(Customer.company_id == company_id)
    if tax_id:
        existing = q.filter(Customer.tax_id == tax_id).first()
        if existing:
            return existing, False
    if email:
        existing = q.filter(Customer.email == email).first()
        if existing:
            return existing, False
    existing = q.filter(Customer.name == name).first()
    if existing:
        return existing, False

    safe_email = email or f"scan+{uuid.uuid4().hex[:10]}@example.com"
    cust = crm_svc.create_customer(
        db,
        user,
        CustomerCreate(name=name, email=safe_email, phone=phone, tax_id=tax_id),
    )
    return cust, True


def _create_invoice_draft(
    db: Session,
    user: User,
    *,
    company_id: int,
    customer_id: int,
    amount: float,
    description: str,
) -> Invoice:
    amt = float(amount or 0)
    if amt <= 0:
        raise HTTPException(status_code=422, detail="Importe inválido para factura.")

    tax_rate = 21.0
    subtotal = round(amt / (1 + tax_rate / 100), 2)
    tax_amount = round(amt - subtotal, 2)
    invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{db.query(func.count(Invoice.id)).scalar() + 1}"

    inv = Invoice(
        invoice_number=invoice_number,
        company_id=company_id,
        customer_id=customer_id,
        invoice_type=InvoiceType.INVOICE,
        status=InvoiceStatus.DRAFT,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=amt,
        amount_due=amt,
        created_by=user.id,
        notes=f"Generada por escaneo QR — {description[:200]}",
    )
    db.add(inv)
    db.flush()

    item = InvoiceItem(
        invoice_id=inv.id,
        description=description[:500],
        quantity=1.0,
        unit_price=subtotal,
        tax_rate=tax_rate,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=amt,
    )
    db.add(item)
    db.flush()
    return inv


def _resolve_customer_ref(
    db: Session,
    user: User,
    *,
    company_id: int,
    customer_ref: str,
) -> Customer:
    ref = (customer_ref or "").strip()
    if not ref:
        raise HTTPException(status_code=422, detail="Referencia de cliente vacía.")
    q = db.query(Customer).filter(Customer.company_id == company_id)
    if ref.isdigit():
        row = q.filter(Customer.id == int(ref)).first()
        if row:
            return row
    row = q.filter(Customer.tax_id == ref).first()
    if row:
        return row
    row = q.filter(Customer.name == ref).first()
    if row:
        return row
    raise HTTPException(status_code=404, detail=f"Cliente no encontrado: {ref}")


def _process_client_qr_action(
    db: Session,
    user: User,
    *,
    company_id: int,
    parsed: Dict[str, Any],
    raw_data: str,
    force_execute: bool = False,
) -> Dict[str, Any]:
    """CLIENT|ID|ACTION — acciones CRM/fichaje desde QR."""
    action = str(parsed.get("action") or "VIEW").upper()
    customer_ref = str(parsed.get("customer_ref") or "").strip()

    if action == "CHECKIN":
        token = raw_data if raw_data.upper().startswith("ZEUSCHECK|") else f"ZEUSCHECK|{customer_ref}|"
        return process_nfc_scan(
            db,
            user,
            text=token,
            company_id=company_id,
            checkin_type="entrada",
            employee_id=customer_ref or None,
        )

    if action == "CREATE":
        name = customer_ref or "Cliente QR"
        cust, created = _find_or_create_customer(
            db,
            user,
            company_id=company_id,
            name=name,
        )
        result = {
            "success": True,
            "executed": True,
            "action": action,
            "customer_id": cust.id,
            "customer_created": created,
            "message": f"Cliente {'creado' if created else 'existente'}: {cust.name}",
        }
        scan = _persist_scan(
            db,
            company_id=company_id,
            user=user,
            scan_type="qr",
            agent_name="ZEUS",
            raw_payload=raw_data,
            parsed=parsed,
            result=result,
        )
        db.commit()
        return {**result, "scan_event_id": scan.id}

    cust = _resolve_customer_ref(db, user, company_id=company_id, customer_ref=customer_ref)
    if action == "PAYMENT":
        return process_qr_scan(
            db,
            user,
            data=f"ZEUS|{cust.name}|0|EUR|{cust.email or ''}",
            company_id=company_id,
            force_execute=force_execute,
        )

    result = {
        "success": True,
        "executed": True,
        "action": action,
        "customer_id": cust.id,
        "customer_name": cust.name,
        "customer_email": cust.email,
        "message": f"Cliente localizado: {cust.name}",
    }
    scan = _persist_scan(
        db,
        company_id=company_id,
        user=user,
        scan_type="qr",
        agent_name="ZEUS",
        raw_payload=raw_data,
        parsed=parsed,
        result=result,
    )
    db.commit()
    return {**result, "scan_event_id": scan.id}


def process_qr_scan(
    db: Session,
    user: User,
    *,
    data: str,
    company_id: Optional[int] = None,
    force_execute: bool = False,
) -> Dict[str, Any]:
    """QR fiscal → cliente + factura + cashflow (RAFAEL). QR fichaje → checkin (AFRODITA)."""
    cid = _company_id(db, user, company_id)
    parsed = _parse_qr_data(data)

    if parsed.get("kind") == "checkin":
        nfc_result = process_nfc_scan(
            db,
            user,
            text=parsed["raw"],
            company_id=cid,
            checkin_type="entrada",
        )
        scan = _persist_scan(
            db,
            company_id=cid,
            user=user,
            scan_type="qr",
            agent_name="AFRODITA",
            raw_payload=data,
            parsed=parsed,
            result=nfc_result,
        )
        db.commit()
        return {**nfc_result, "scan_event_id": scan.id, "routed": "checkin"}

    if parsed.get("kind") == "client_action":
        out = _process_client_qr_action(
            db,
            user,
            company_id=cid,
            parsed=parsed,
            raw_data=data,
            force_execute=force_execute,
        )
        return {**out, "routed": "client_action"}

    emit_scan_detected(
        user_id=user.id,
        user_email=getattr(user, "email", None),
        company_id=cid,
        scan_type="qr",
        agent_name="RAFAEL",
        trigger="qr_scan_detected",
        details=parsed,
        db=db,
    )

    customer_name = str(parsed.get("customer_name") or "Cliente QR").strip()
    amount = float(parsed.get("amount") or 0)
    cust, created = _find_or_create_customer(
        db,
        user,
        company_id=cid,
        name=customer_name,
        email=parsed.get("email"),
    )

    approval_payload = {
        "customer_id": cust.id,
        "amount": amount,
        "currency": parsed.get("currency", "EUR"),
        "source": "qr_scan",
    }
    needs_approval = amount >= 500 and requires_approval("register_payment", {"amount": amount})

    if needs_approval and not force_execute:
        approval = request_approval(
            db,
            user=user,
            company_id=cid,
            agent_name="RAFAEL",
            action_type="generate_invoice",
            payload=approval_payload,
        )
        result = {
            "success": True,
            "executed": False,
            "needs_approval": True,
            "approval_id": approval.id,
            "customer_id": cust.id,
            "customer_created": created,
            "message": f"Factura QR ({amount:.2f} €) pendiente de aprobación humana.",
        }
        scan = _persist_scan(db, company_id=cid, user=user, scan_type="qr", agent_name="RAFAEL", raw_payload=data, parsed=parsed, result=result)
        db.commit()
        return {**result, "scan_event_id": scan.id}

    invoice_id = None
    cashflow_id = None
    if amount > 0:
        inv = _create_invoice_draft(
            db,
            user,
            company_id=cid,
            customer_id=cust.id,
            amount=amount,
            description=f"Servicio {customer_name}",
        )
        invoice_id = inv.id
        emit_invoice_generated(
            user_id=user.id,
            user_email=getattr(user, "email", None),
            company_id=cid,
            invoice_id=inv.id,
            file_path="scan_flow",
            file_size=0,
            db=db,
        )
        emit_cashflow_updated(
            user_id=user.id,
            user_email=getattr(user, "email", None),
            company_id=cid,
            amount=amount,
            direction="in",
            source="QR_SCAN",
            customer_id=cust.id,
            invoice_id=inv.id,
            payment_method="qr",
            db=db,
        )
        cashflow_id = "ledger"

    result = {
        "success": True,
        "executed": True,
        "needs_approval": False,
        "customer_id": cust.id,
        "customer_created": created,
        "invoice_id": invoice_id,
        "amount": amount,
        "cashflow_updated": cashflow_id is not None,
        "message": f"QR procesado: cliente {cust.name}" + (f", factura {invoice_id}" if invoice_id else ""),
    }
    scan = _persist_scan(db, company_id=cid, user=user, scan_type="qr", agent_name="RAFAEL", raw_payload=data, parsed=parsed, result=result)
    db.commit()
    return {**result, "scan_event_id": scan.id}


def process_nfc_scan(
    db: Session,
    user: User,
    *,
    text: Optional[str] = None,
    payload_hex: Optional[str] = None,
    company_id: Optional[int] = None,
    checkin_type: str = "entrada",
    employee_id: Optional[str] = None,
) -> Dict[str, Any]:
    """NFC → fichaje real (AFRODITA) + coste laboral."""
    cid = _company_id(db, user, company_id)
    decoded = (text or "").strip()
    if not decoded and payload_hex:
        try:
            decoded = bytes.fromhex(payload_hex.strip()).decode("utf-8", errors="ignore").strip()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="payload_hex NFC inválido.") from exc
    if not decoded:
        raise HTTPException(status_code=422, detail="Contenido NFC vacío.")

    parsed: Dict[str, Any] = {"raw": decoded, "payload_hex": payload_hex}
    emp_code = employee_id
    if decoded.upper().startswith("ZEUSCHECK|"):
        parts = decoded.split("|")
        emp_code = emp_code or (parts[1] if len(parts) > 1 else None)
        parsed["employee_id"] = emp_code
        parsed["kind"] = "employee_checkin"
    else:
        parsed["kind"] = "generic_nfc"
        parsed["decoded_text"] = decoded

    if not emp_code:
        raise HTTPException(
            status_code=422,
            detail="No se identificó empleado. Formato esperado: ZEUSCHECK|CODIGO_EMPLEADO|timestamp",
        )

    emit_scan_detected(
        user_id=user.id,
        user_email=getattr(user, "email", None),
        company_id=cid,
        scan_type="nfc",
        agent_name="AFRODITA",
        trigger="nfc_detected",
        details=parsed,
        db=db,
    )

    meta = {"nfc_token": decoded, "qr_token": decoded, "source": "nfc_scan"}
    checkin_out = register_checkin(
        db,
        user=user,
        company_id=cid,
        employee_id=str(emp_code),
        checkin_type=checkin_type,
        method="nfc",
        metadata=meta,
    )

    result = {
        "success": True,
        "executed": True,
        "employee_id": emp_code,
        "checkin_type": checkin_type,
        "session": checkin_out,
        "cost_calculated": checkin_out.get("cost_eur") is not None,
        "message": f"Fichaje NFC {checkin_type} registrado para {emp_code}.",
    }
    scan = _persist_scan(
        db,
        company_id=cid,
        user=user,
        scan_type="nfc",
        agent_name="AFRODITA",
        raw_payload=decoded,
        parsed=parsed,
        result=result,
    )
    db.commit()
    return {**result, "scan_event_id": scan.id}


def process_dni_scan(
    db: Session,
    user: User,
    *,
    mrz: str,
    company_id: Optional[int] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    ocr_relaxed: bool = False,
) -> Dict[str, Any]:
    """DNI MRZ → cliente CRM + scoring + lead (ZEUS)."""
    cid = _company_id(db, user, company_id)
    normalized_mrz = (mrz or "").strip()
    normalized_email = (email or "").strip() or None
    normalized_phone = (phone or "").strip() or None
    try:
        identity = parse_mrz_ocr(normalized_mrz) if ocr_relaxed else parse_mrz(normalized_mrz)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    emit_scan_detected(
        user_id=user.id,
        user_email=getattr(user, "email", None),
        company_id=cid,
        scan_type="dni",
        agent_name="ZEUS",
        trigger="dni_detected",
        details=identity,
        db=db,
    )

    full_name = identity.get("full_name") or identity.get("surname") or "Cliente DNI"
    tax_id = identity.get("document_number")
    cust, created = _find_or_create_customer(
        db,
        user,
        company_id=cid,
        name=full_name,
        email=normalized_email,
        tax_id=tax_id,
        phone=normalized_phone,
    )

    scoring = score_customer(db, user=user, customer_id=cust.id)
    lead = create_lead(
        db,
        user=user,
        name=full_name,
        email=normalized_email or cust.email,
        phone=normalized_phone,
        sector="dni_scan",
        estimated_value=50.0,
    )
    lead.converted_customer_id = cust.id
    db.add(lead)
    db.flush()
    lead_score = score_lead(db, user=user, lead_id=lead.id)

    result = {
        "success": True,
        "executed": True,
        "customer_id": cust.id,
        "customer_created": created,
        "identity": identity,
        "lead_id": lead.id,
        "lead_score": lead_score.get("lead_score"),
        "customer_priority": lead_score.get("customer_priority"),
        "next_best_action": lead_score.get("next_best_action"),
        "scoring": scoring,
        "message": f"Cliente creado desde DNI: {full_name} (score {lead_score.get('lead_score')})",
    }
    scan = _persist_scan(
        db,
        company_id=cid,
        user=user,
        scan_type="dni",
        agent_name="ZEUS",
        raw_payload=normalized_mrz[:4000],
        parsed=identity,
        result=result,
    )
    db.commit()
    return {**result, "scan_event_id": scan.id}
