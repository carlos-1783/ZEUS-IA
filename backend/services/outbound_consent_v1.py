"""Envios salientes a personas (email / WhatsApp) solo con consentimiento, por empresa.

Fase 2 / auditoria final (#3, #4, #15). Reglas:
- Un cliente solo recibe comunicaciones comerciales si tiene `marketing_consent` registrado y
  no se ha dado de baja (`marketing_unsubscribed_at`). Por defecto nadie tiene consentimiento.
- Los envios directos desde la API solo van a clientes (con consentimiento) o empleados activos
  de la empresa del usuario; envios a cualquier destinatario solo para superusuario (plataforma).
- Limite de envios por empresa y canal en una ventana real en BD (tabla outbound_messages).
- Baja real: enlace con token HMAC (SECRET_KEY) ligado a empresa+cliente; el endpoint publico
  marca la baja en BD. Sin PUBLIC_BASE_URL no se puede construir el enlace -> no se envia.
- Logs con PII minimizada: destinatario en hash + enmascarado; nunca el cuerpo del mensaje.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company_employee import CompanyEmployee
from app.models.customer import Customer
from app.models.outbound_message import OutboundMessage
from app.models.user import User

logger = logging.getLogger(__name__)

CHANNEL_EMAIL = "email"
CHANNEL_WHATSAPP = "whatsapp"

_UNSUB_PREFIX = "ZEUSUNSUB1"
UNSUBSCRIBE_PATH = "/api/v1/p/unsubscribe"


def _env_int(name: str, default: int) -> int:
    try:
        v = int((os.getenv(name) or "").strip() or default)
        return v if v > 0 else default
    except ValueError:
        return default


def direct_limit_per_hour() -> int:
    """Envios directos por empresa y canal en la ultima hora."""
    return _env_int("OUTBOUND_DIRECT_LIMIT_PER_HOUR", 30)


# ------------------------------------------------------------------ normalizacion / PII


def normalize_email(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


def normalize_phone(value: Optional[str], default_country_code: str = "+34") -> str:
    """Solo digitos y '+'; sin '+' se antepone el prefijo por defecto (mismo criterio que Twilio)."""
    s = str(value or "").strip()
    if s.lower().startswith("whatsapp:"):
        s = s[9:]
    s = "".join(c for c in s if c.isdigit() or c == "+")
    if not s or not any(c.isdigit() for c in s):
        return ""
    if s.startswith("+"):
        return "+" + s[1:].replace("+", "")
    s = s.replace("+", "")
    if s.startswith("00"):
        return "+" + s[2:]
    if s.startswith("0") and len(s) > 9:
        s = s.lstrip("0")
    return default_country_code + s


def normalize_recipient(channel: str, value: Optional[str]) -> str:
    return normalize_email(value) if channel == CHANNEL_EMAIL else normalize_phone(value)


def recipient_hash(channel: str, value: Optional[str]) -> str:
    norm = normalize_recipient(channel, value)
    return hashlib.sha256(f"{channel}|{norm}".encode("utf-8")).hexdigest()


def mask_phone(value: Optional[str]) -> str:
    norm = normalize_phone(value)
    if len(norm) <= 4:
        return "***"
    return norm[:3] + "*" * max(len(norm) - 6, 3) + norm[-3:]


def mask_email(value: Optional[str]) -> str:
    norm = normalize_email(value)
    if "@" not in norm:
        return "***"
    local, domain = norm.split("@", 1)
    return (local[:1] or "*") + "***@" + domain


def mask_recipient(channel: str, value: Optional[str]) -> str:
    return mask_email(value) if channel == CHANNEL_EMAIL else mask_phone(value)


# ------------------------------------------------------------------ consentimiento


def customer_marketing_allowed(customer: Customer) -> bool:
    return (
        bool(getattr(customer, "marketing_consent", False))
        and getattr(customer, "marketing_unsubscribed_at", None) is None
        and getattr(customer, "is_active", True) is not False
    )


def set_marketing_consent(
    db: Session, user: User, customer_id: int, *, granted: bool, source: str
) -> Customer:
    """Registra (o retira) el consentimiento comercial de un cliente de la empresa del usuario."""
    import services.crm_office_service as crm_svc

    customer = crm_svc.resolve_customer(db, user, customer_id)  # 404 si es de otra empresa
    now = datetime.now(timezone.utc)
    customer.marketing_consent = bool(granted)
    customer.marketing_consent_source = (source or "manual")[:50]
    if granted:
        customer.marketing_consent_at = now
        customer.marketing_unsubscribed_at = None
    else:
        customer.marketing_unsubscribed_at = now
    db.add(customer)
    db.commit()
    db.refresh(customer)
    cid = crm_svc.effective_company_id_for_crm(db, user, customer)
    crm_svc.log_activity(
        db,
        company_id=cid,
        user_id=user.id,
        customer_id=customer.id,
        record_id=None,
        action="marketing_consent_granted" if granted else "marketing_consent_revoked",
        summary=("Consentimiento comercial registrado" if granted else "Consentimiento comercial retirado")
        + f" ({customer.marketing_consent_source})",
        payload={"customer_id": customer.id, "source": customer.marketing_consent_source},
    )
    logger.info(
        "marketing_consent company_id=%s customer_id=%s granted=%s source=%s user_id=%s",
        cid, customer.id, granted, customer.marketing_consent_source, user.id,
    )
    return customer


# ------------------------------------------------------------------ baja (unsubscribe)


def _unsub_sig(company_id: int, customer_id: int) -> str:
    key = (settings.SECRET_KEY or "").encode("utf-8")
    msg = f"zeus-unsubscribe|{int(company_id)}|{int(customer_id)}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:32]


def issue_unsubscribe_token(company_id: int, customer_id: int) -> str:
    return f"{_UNSUB_PREFIX}.{int(company_id)}.{int(customer_id)}.{_unsub_sig(company_id, customer_id)}"


def parse_unsubscribe_token(token: Optional[str]) -> Optional[Tuple[int, int]]:
    parts = str(token or "").strip().split(".")
    if len(parts) != 4 or parts[0] != _UNSUB_PREFIX or not parts[1].isdigit() or not parts[2].isdigit():
        return None
    company_id, customer_id = int(parts[1]), int(parts[2])
    if not hmac.compare_digest(parts[3], _unsub_sig(company_id, customer_id)):
        return None
    return company_id, customer_id


def unsubscribe_url(company_id: int, customer_id: int) -> Optional[str]:
    """URL publica de baja. None si PUBLIC_BASE_URL no esta configurado (no se inventa dominio)."""
    base = (settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}{UNSUBSCRIBE_PATH}?token={quote(issue_unsubscribe_token(company_id, customer_id))}"


def unsubscribe_footer_html(url: str, business_name: str) -> str:
    return (
        '<hr><p style="font-size:12px;color:#666">Recibes este correo porque diste tu consentimiento a '
        f"{escape(business_name)} para recibir comunicaciones comerciales. "
        f'<a href="{escape(url, quote=True)}">Darme de baja</a></p>'
    )


def apply_unsubscribe(db: Session, token: Optional[str]) -> Optional[Customer]:
    """Marca la baja del cliente del token (solo dentro de su empresa). None si el token no vale."""
    parsed = parse_unsubscribe_token(token)
    if not parsed:
        logger.warning("unsubscribe rechazado: token no valido")
        return None
    company_id, customer_id = parsed
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.company_id == company_id)
        .first()
    )
    if customer is None:
        logger.warning("unsubscribe: cliente no encontrado company_id=%s customer_id=%s", company_id, customer_id)
        return None
    if customer.marketing_unsubscribed_at is None or customer.marketing_consent:
        customer.marketing_consent = False
        customer.marketing_unsubscribed_at = datetime.now(timezone.utc)
        customer.marketing_consent_source = "unsubscribe_link"
        db.add(customer)
        db.commit()
        db.refresh(customer)
        try:
            import services.crm_office_service as crm_svc

            crm_svc.log_activity(
                db,
                company_id=company_id,
                user_id=None,
                customer_id=customer.id,
                record_id=None,
                action="marketing_unsubscribed",
                summary="El cliente se dio de baja de las comunicaciones comerciales",
                payload={"customer_id": customer.id, "source": "unsubscribe_link"},
            )
        except Exception:
            logger.exception("unsubscribe: no se pudo registrar la actividad customer_id=%s", customer.id)
            db.rollback()
    logger.info("unsubscribe company_id=%s customer_id=%s", company_id, customer.id)
    return customer


# ------------------------------------------------------------------ registro / limites


def record_outbound(
    db: Session,
    *,
    company_id: Optional[int],
    user_id: Optional[int],
    channel: str,
    purpose: str,
    recipient: Optional[str],
    status_value: str,
    detail: Optional[str] = None,
    recipient_kind: Optional[str] = None,
    recipient_ref_id: Optional[int] = None,
    commit: bool = True,
) -> OutboundMessage:
    row = OutboundMessage(
        company_id=company_id,
        user_id=user_id,
        channel=channel,
        purpose=purpose,
        recipient_kind=recipient_kind,
        recipient_ref_id=recipient_ref_id,
        recipient_hash=recipient_hash(channel, recipient),
        recipient_masked=mask_recipient(channel, recipient)[:120],
        status=status_value,
        detail=(detail or None) and str(detail)[:300],
    )
    db.add(row)
    if commit:
        db.commit()
    logger.info(
        "outbound company_id=%s user_id=%s channel=%s purpose=%s to=%s status=%s",
        company_id, user_id, channel, purpose, row.recipient_masked, status_value,
    )
    return row


def count_recent(
    db: Session,
    *,
    window: timedelta,
    channel: Optional[str] = None,
    purpose: Optional[str] = None,
    company_id: Optional[int] = None,
    recipient: Optional[str] = None,
    statuses: Tuple[str, ...] = ("sent", "failed"),
) -> int:
    since = datetime.now(timezone.utc) - window
    q = db.query(OutboundMessage).filter(
        OutboundMessage.created_at >= since, OutboundMessage.status.in_(statuses)
    )
    if channel:
        q = q.filter(OutboundMessage.channel == channel)
    if purpose:
        q = q.filter(OutboundMessage.purpose == purpose)
    if company_id is not None:
        q = q.filter(OutboundMessage.company_id == company_id)
    if recipient is not None and channel:
        q = q.filter(OutboundMessage.recipient_hash == recipient_hash(channel, recipient))
    return q.count()


def enforce_company_direct_limit(db: Session, company_id: int, channel: str) -> None:
    limit = direct_limit_per_hour()
    used = count_recent(db, window=timedelta(hours=1), channel=channel, purpose="direct", company_id=company_id)
    if used >= limit:
        logger.warning("outbound limite empresa company_id=%s channel=%s used=%s limit=%s", company_id, channel, used, limit)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Limite de envios por {channel} alcanzado para tu empresa ({limit} por hora). Prueba mas tarde.",
        )


# ------------------------------------------------------------------ destinatario de envio directo


def _employee_by_phone(db: Session, company_id: int, norm: str) -> Optional[CompanyEmployee]:
    rows = (
        db.query(CompanyEmployee)
        .filter(
            CompanyEmployee.company_id == company_id,
            CompanyEmployee.is_active.is_(True),
            CompanyEmployee.phone.isnot(None),
        )
        .all()
    )
    return next((e for e in rows if normalize_phone(e.phone) == norm), None)


def _employee_by_email(db: Session, company_id: int, norm: str) -> Optional[CompanyEmployee]:
    """Empleado activo de la empresa cuyo usuario vinculado tiene ese email."""
    rows = (
        db.query(CompanyEmployee, User.email)
        .join(User, User.id == CompanyEmployee.user_id)
        .filter(
            CompanyEmployee.company_id == company_id,
            CompanyEmployee.is_active.is_(True),
            User.email.isnot(None),
        )
        .all()
    )
    return next((e for e, email in rows if normalize_email(email) == norm), None)


def resolve_direct_recipient(db: Session, user: User, channel: str, value: str) -> Dict[str, Any]:
    """Comprueba que el destinatario de un envio directo es legitimo para este usuario.

    Devuelve {"company_id", "kind", "ref_id"}; lanza 403 (y registra el bloqueo) si no.
    - Superusuario: envio de plataforma a cualquier destinatario (company_id None).
    - Resto: cliente de SU empresa con consentimiento comercial y sin baja, o empleado activo
      de su empresa. Un cliente de otra empresa es como un desconocido: 403.
    """
    import services.crm_office_service as crm_svc

    norm = normalize_recipient(channel, value)
    if not norm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Destinatario no valido.")

    if getattr(user, "is_superuser", False):
        return {"company_id": None, "kind": "platform", "ref_id": None}

    company_id = crm_svc.primary_company_id(db, user)
    if company_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El usuario no tiene empresa asignada.")

    customers = db.query(Customer).filter(Customer.company_id == company_id)
    if channel == CHANNEL_EMAIL:
        customers = customers.filter(Customer.email.isnot(None)).all()
        matches = [c for c in customers if normalize_email(c.email) == norm]
    else:
        customers = customers.filter(Customer.phone.isnot(None)).all()
        matches = [c for c in customers if normalize_phone(c.phone) == norm]

    allowed = next((c for c in matches if customer_marketing_allowed(c)), None)
    if allowed is not None:
        return {"company_id": company_id, "kind": "customer", "ref_id": allowed.id}

    employee = (
        _employee_by_email(db, company_id, norm)
        if channel == CHANNEL_EMAIL
        else _employee_by_phone(db, company_id, norm)
    )
    if employee:
        return {"company_id": company_id, "kind": "employee", "ref_id": employee.id}

    reason = (
        "cliente sin consentimiento comercial o dado de baja"
        if matches
        else "no es cliente ni empleado de tu empresa"
    )
    record_outbound(
        db,
        company_id=company_id,
        user_id=user.id,
        channel=channel,
        purpose="direct",
        recipient=value,
        status_value="blocked",
        detail=reason,
        recipient_kind="customer" if matches else None,
        recipient_ref_id=matches[0].id if matches else None,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Envio bloqueado: el destinatario {reason}.",
    )
