"""Lógica CRM oficina: multi-empresa, expedientes, cobros vía persist_fiscal_sale, actividad."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.company import UserCompany
from app.models.customer import Customer, ContactPerson
from app.models.crm_office import CrmActivityLog, CrmSaleLink, CustomerRecord
from app.models.user import User
from app.schemas.customer import CustomerCreate
from services.fiscal_engine import build_fiscal_items_from_cart, get_fiscal_profile, persist_fiscal_sale
from services.tpv_service import PaymentMethod

logger = logging.getLogger(__name__)


def company_ids_for_user(db: Session, user: User) -> List[int]:
    rows = db.query(UserCompany.company_id).filter(UserCompany.user_id == user.id).all()
    return [r[0] for r in rows]


def primary_company_id(db: Session, user: User) -> Optional[int]:
    uc = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    return uc.company_id if uc else None


def _customer_scope_filter(user: User, cids: List[int]):
    if not cids:
        return Customer.owner_user_id == user.id
    return or_(
        Customer.company_id.in_(cids),
        and_(Customer.company_id.is_(None), Customer.owner_user_id == user.id),
    )


def resolve_customer(db: Session, user: User, customer_id: int) -> Customer:
    cids = company_ids_for_user(db, user)
    q = db.query(Customer).filter(Customer.id == customer_id).filter(_customer_scope_filter(user, cids))
    row = q.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado")
    return row


def list_customers(db: Session, user: User) -> List[Customer]:
    cids = company_ids_for_user(db, user)
    q = (
        db.query(Customer)
        .options(joinedload(Customer.contacts))
        .filter(_customer_scope_filter(user, cids))
        .order_by(Customer.name.asc())
    )
    return q.all()


def assert_email_unique_in_company(
    db: Session, company_id: Optional[int], email: Optional[str], exclude_customer_id: Optional[int] = None
) -> None:
    if not email or not str(email).strip():
        return
    email = str(email).strip().lower()
    if company_id is not None:
        q = db.query(Customer).filter(
            Customer.company_id == company_id,
            Customer.email.isnot(None),
            Customer.email == email,
        )
    else:
        q = db.query(Customer).filter(
            Customer.company_id.is_(None),
            Customer.email.isnot(None),
            Customer.email == email,
        )
    if exclude_customer_id is not None:
        q = q.filter(Customer.id != exclude_customer_id)
    if q.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un cliente con ese email en tu empresa.",
        )


def effective_company_id_for_crm(db: Session, user: User, cust: Customer) -> int:
    """Empresa efectiva para expedientes/actividad (FK no nulo en tablas CRM)."""
    cid = cust.company_id or primary_company_id(db, user)
    if cid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere una empresa asociada para usar expedientes y actividad CRM.",
        )
    cids = company_ids_for_user(db, user)
    if cids and cid not in cids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a la empresa del cliente")
    return cid


def log_activity(
    db: Session,
    *,
    company_id: int,
    user_id: Optional[int],
    customer_id: Optional[int],
    record_id: Optional[int],
    action: str,
    summary: Optional[str],
    payload: Optional[Dict[str, Any]] = None,
    commit: bool = True,
) -> None:
    row = CrmActivityLog(
        company_id=company_id,
        user_id=user_id,
        customer_id=customer_id,
        customer_record_id=record_id,
        action=action,
        summary=summary,
        payload=payload or {},
    )
    db.add(row)
    if commit:
        db.commit()
    else:
        db.flush()


def create_customer(db: Session, user: User, customer_in: CustomerCreate) -> Customer:
    """Alta de cliente CRM (multi-empresa, contactos opcionales, log de actividad)."""
    cid = primary_company_id(db, user)
    assert_email_unique_in_company(db, cid, customer_in.email)

    contacts_data = list(customer_in.contacts or [])
    customer = Customer(
        name=customer_in.name,
        email=customer_in.email,
        phone=customer_in.phone,
        address=customer_in.address,
        tax_id=customer_in.tax_id,
        notes=customer_in.notes,
        is_active=customer_in.is_active,
        is_company=customer_in.is_company,
        metadata_=customer_in.metadata,
        company_id=cid,
        owner_user_id=user.id,
    )
    db.add(customer)
    db.flush()

    for c in contacts_data:
        db.add(ContactPerson(customer_id=customer.id, **c.model_dump()))

    db.commit()
    db.refresh(customer)

    log_cid = customer.company_id or primary_company_id(db, user)
    if log_cid is not None:
        log_activity(
            db,
            company_id=log_cid,
            user_id=user.id,
            customer_id=customer.id,
            record_id=None,
            action="customer_created",
            summary=f"Cliente creado: {customer.name}",
            payload={"customer_id": customer.id},
        )

    return customer


def list_records(db: Session, user: User, customer_id: int) -> List[CustomerRecord]:
    cust = resolve_customer(db, user, customer_id)
    return (
        db.query(CustomerRecord)
        .filter(CustomerRecord.customer_id == cust.id)
        .order_by(CustomerRecord.id.desc())
        .all()
    )


def resolve_record(db: Session, user: User, record_id: int) -> CustomerRecord:
    rec = db.query(CustomerRecord).filter(CustomerRecord.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expediente no encontrado")
    cust = resolve_customer(db, user, rec.customer_id)
    cids = company_ids_for_user(db, user)
    if cids:
        if rec.company_id not in cids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al expediente")
    else:
        if cust.owner_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al expediente")
    return rec


def list_activity_for_customer(db: Session, user: User, customer_id: int, limit: int = 100) -> List[CrmActivityLog]:
    cust = resolve_customer(db, user, customer_id)
    cid = effective_company_id_for_crm(db, user, cust)
    q = (
        db.query(CrmActivityLog)
        .filter(CrmActivityLog.customer_id == cust.id)
        .filter(CrmActivityLog.company_id == cid)
        .order_by(CrmActivityLog.id.desc())
        .limit(limit)
    )
    return q.all()


def create_record(
    db: Session,
    user: User,
    customer_id: int,
    *,
    title: str,
    status: str = "open",
    amount: Decimal = Decimal("0"),
    notes: Optional[str] = None,
) -> CustomerRecord:
    cust = resolve_customer(db, user, customer_id)
    cid = effective_company_id_for_crm(db, user, cust)
    rec = CustomerRecord(
        company_id=cid,
        customer_id=cust.id,
        title=title.strip()[:255] or "Expediente",
        status=(status or "open").strip()[:32] or "open",
        amount=amount,
        notes=notes,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    log_activity(
        db,
        company_id=cid,
        user_id=user.id,
        customer_id=cust.id,
        record_id=rec.id,
        action="record_created",
        summary=f"Expediente creado: {rec.title}",
        payload={"customer_record_id": rec.id},
    )
    return rec


def update_record(
    db: Session,
    user: User,
    record_id: int,
    *,
    title: Optional[str] = None,
    status: Optional[str] = None,
    amount: Optional[Decimal] = None,
    notes: Optional[str] = None,
) -> CustomerRecord:
    rec = resolve_record(db, user, record_id)
    cust = resolve_customer(db, user, rec.customer_id)
    cid = effective_company_id_for_crm(db, user, cust)
    if rec.company_id != cid:
        raise HTTPException(status_code=403, detail="Sin acceso al expediente")
    if title is not None:
        rec.title = title.strip()[:255] or rec.title
    if status is not None:
        rec.status = status.strip()[:32] or rec.status
    if amount is not None:
        rec.amount = amount
    if notes is not None:
        rec.notes = notes
    rec.updated_at = datetime.now(timezone.utc)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    log_activity(
        db,
        company_id=cid,
        user_id=user.id,
        customer_id=cust.id,
        record_id=rec.id,
        action="record_updated",
        summary=f"Expediente actualizado: {rec.title}",
        payload={},
    )
    return rec


def delete_record(db: Session, user: User, record_id: int) -> None:
    rec = resolve_record(db, user, record_id)
    cust = resolve_customer(db, user, rec.customer_id)
    cid = effective_company_id_for_crm(db, user, cust)
    if rec.company_id != cid:
        raise HTTPException(status_code=403, detail="Sin acceso al expediente")
    rid = rec.id
    title = rec.title
    db.delete(rec)
    db.commit()
    log_activity(
        db,
        company_id=cid,
        user_id=user.id,
        customer_id=cust.id,
        record_id=None,
        action="record_deleted",
        summary=f"Expediente eliminado: {title}",
        payload={"deleted_customer_record_id": rid},
    )


def register_record_charge(
    db: Session,
    user: User,
    record_id: int,
    *,
    base_amount: Decimal,
    payment_method: str,
    description: str,
    iva_rate: float = 21.0,
    consumption_type: str = "onsite",
) -> Dict[str, Any]:
    """Una línea fiscal + persist_fiscal_sale + vínculo CRM (sin duplicar motor TPV)."""
    rec = resolve_record(db, user, record_id)
    cust = resolve_customer(db, user, rec.customer_id)
    if cust.company_id != rec.company_id:
        raise HTTPException(status_code=400, detail="Inconsistencia cliente/expediente")

    cid = rec.company_id
    if base_amount <= Decimal("0"):
        raise HTTPException(status_code=400, detail="El importe base debe ser mayor que cero")

    try:
        pm = PaymentMethod(payment_method.lower().strip())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Método de pago no válido. Use: {[m.value for m in PaymentMethod]}",
        )

    from services.employee_work_session_service import get_active_work_session_id_for_sale

    work_sid = get_active_work_session_id_for_sale(db, user)

    profile = get_fiscal_profile(db, user.id)
    apply_recargo = bool(getattr(profile, "apply_recargo_equivalencia", False)) if profile else False
    recargo_rate = float(getattr(profile, "recargo_rate", 0) or 0) if profile else None

    line_name = (description or f"Expediente #{rec.id}").strip()[:200] or f"Expediente #{rec.id}"
    cart_line = {
        "product_id": "CRM_OFFICE",
        "name": line_name,
        "quantity": 1,
        "price": float(base_amount),
        "iva_rate": float(iva_rate),
    }
    fiscal_items = build_fiscal_items_from_cart(
        [cart_line],
        apply_recargo=apply_recargo,
        recargo_rate=recargo_rate,
        consumption_type=consumption_type,
    )
    ticket_id = f"CRM_{uuid.uuid4().hex[:20].upper()}"
    customer_data: Dict[str, Any] = {
        "source": "office_crm",
        "crm_customer_id": cust.id,
        "crm_record_id": rec.id,
        "customer_name": cust.name,
    }

    logger.info(
        "CMR cobro iniciado record_id=%s customer_id=%s company_id=%s amount=%s ticket=%s",
        rec.id,
        cust.id,
        cid,
        base_amount,
        ticket_id,
    )

    from services.rafael_service import (
        RafaelFiscalError,
        build_cmr_fiscal_ticket,
        persist_sale as rafael_persist_sale,
    )

    try:
        tpv_sale_id = persist_fiscal_sale(
            db,
            user_id=user.id,
            ticket_id=ticket_id,
            document_type="ticket",
            payment_method=pm.value,
            fiscal_items=fiscal_items,
            consumption_type=consumption_type,
            company_id=cid,
            work_session_id=work_sid,
            customer_data=customer_data,
            auto_commit=False,
        )
        ticket = build_cmr_fiscal_ticket(
            ticket_id=ticket_id,
            service_name=line_name,
            cart_line=cart_line,
            fiscal_items=fiscal_items,
            payment_method=pm.value,
            company_id=cid,
            customer_id=cust.id,
            customer_name=cust.name,
            record_id=rec.id,
        )
        rafael_result = rafael_persist_sale(
            db=db,
            user_id=user.id,
            company_id=cid,
            ticket=ticket,
            tpv_sale_id=tpv_sale_id,
            user_email=getattr(user, "email", None),
            source="CMR",
        )

        link = CrmSaleLink(
            company_id=cid,
            customer_id=cust.id,
            customer_record_id=rec.id,
            tpv_sale_id=tpv_sale_id,
            user_id=user.id,
        )
        rec.updated_at = datetime.now(timezone.utc)
        if rec.status in ("open", "in_progress"):
            rec.status = "paid"
        db.add(link)
        db.add(rec)
        db.commit()

        logger.info(
            "CMR cobro confirmado ticket=%s sale_id=%s rafael_ok=true",
            ticket_id,
            tpv_sale_id,
        )
    except RafaelFiscalError as exc:
        db.rollback()
        logger.error(
            "CMR cobro revertido: RAFAEL falló record_id=%s ticket=%s error=%s",
            rec.id,
            ticket_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo registrar el cobro en RAFAEL: {exc}",
        ) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("register_record_charge persistencia fiscal record_id=%s", rec.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar el cobro fiscal. Inténtelo de nuevo.",
        ) from exc

    log_activity(
        db,
        company_id=cid,
        user_id=user.id,
        customer_id=cust.id,
        record_id=rec.id,
        action="payment_created",
        summary=f"Cobro CMR registrado en RAFAEL ({pm.value}) ticket {ticket_id}",
        payload={
            "tpv_sale_id": tpv_sale_id,
            "ticket_id": ticket_id,
            "base_amount": str(base_amount),
            "rafael_document_id": rafael_result.get("fiscal_document_id"),
            "source": "CMR",
        },
    )

    try:
        from services.event_bus import emit_payment_created

        totals = ticket.get("totals") or {}
        emit_payment_created(
            user_id=user.id,
            user_email=getattr(user, "email", None),
            company_id=cid,
            customer_id=cust.id,
            ticket_id=ticket_id,
            tpv_sale_id=tpv_sale_id,
            payment_method=pm.value,
            amount=totals.get("total"),
            service_name=line_name,
            db=db,
        )
    except Exception:
        logger.exception("emit_payment_created falló (cobro ya confirmado) ticket=%s", ticket_id)

    return {
        "success": True,
        "tpv_sale_id": tpv_sale_id,
        "ticket_id": ticket_id,
        "customer_id": cust.id,
        "customer_record_id": rec.id,
        "accounting_sent": True,
        "fiscal_document_id": rafael_result.get("fiscal_document_id"),
    }
