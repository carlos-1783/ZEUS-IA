"""
Web pública por cliente (Opción B para todos).
GET /p/{slug}/info → info negocio y si acepta reservas.
POST /p/{slug}/reservations → crear reserva (público, sin auth) + confirmación WhatsApp si está configurado.
"""
import logging
from html import escape

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional

from app.db.session import get_db
from app.models.user import User
from app.models.reservation import Reservation
from services.tpv_operator_context import primary_company_id
from services.thalos_request_guard_v1 import thalos_anonymous_guard

router = APIRouter()
logger = logging.getLogger(__name__)


class PublicSiteInfoResponse(BaseModel):
    name: str
    reservations_enabled: bool


class CreateReservationRequest(BaseModel):
    guest_name: str
    guest_phone: str
    guest_email: Optional[str] = None
    reservation_date: str  # YYYY-MM-DD
    reservation_time: str  # "20:00"
    num_guests: int = 2
    notes: Optional[str] = None
    # Casilla explicita del formulario: sin ella NO se envia confirmacion por WhatsApp.
    whatsapp_consent: bool = False


def _unsubscribe_page(title: str, text: str, form_token: Optional[str] = None, code: int = 200) -> HTMLResponse:
    form = ""
    if form_token:
        form = (
            f'<form method="post" action="?token={escape(form_token, quote=True)}">'
            '<button type="submit">Confirmar baja</button></form>'
        )
    html = (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title></head><body><h1>{escape(title)}</h1><p>{escape(text)}</p>{form}</body></html>"
    )
    return HTMLResponse(html, status_code=code)


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_page(token: str = Query(..., max_length=200), db: Session = Depends(get_db)):
    """Enlace de baja del pie de los correos. GET solo muestra la confirmacion (los clientes de
    correo precargan enlaces); la baja se hace con POST."""
    from services.outbound_consent_v1 import parse_unsubscribe_token

    if not parse_unsubscribe_token(token):
        return _unsubscribe_page("Enlace no valido", "Este enlace de baja no es valido.", code=400)
    return _unsubscribe_page(
        "Darse de baja",
        "Pulsa el boton para dejar de recibir comunicaciones comerciales de este negocio.",
        form_token=token,
    )


@router.post("/unsubscribe", response_class=HTMLResponse, dependencies=[Depends(thalos_anonymous_guard)])
def unsubscribe_confirm(token: str = Query(..., max_length=200), db: Session = Depends(get_db)):
    """Marca la baja comercial del cliente del token (firmado, ligado a empresa y cliente)."""
    from services.outbound_consent_v1 import apply_unsubscribe

    customer = apply_unsubscribe(db, token)
    if customer is None:
        return _unsubscribe_page("Enlace no valido", "Este enlace de baja no es valido.", code=400)
    return _unsubscribe_page("Baja registrada", "No recibiras mas comunicaciones comerciales de este negocio.")


def _get_user_by_slug(db: Session, slug: str) -> Optional[User]:
    """Titular de la web publica `slug`. RLS: peticion anonima -> el titular se resuelve con la funcion
    acotada public_site_user_id_by_slug() (0071: solo devuelve el id si la web esta habilitada y el
    usuario activo) y la sesion pasa a actuar SOLO con la empresa de la web (la primaria del titular, la
    misma en la que se crean las reservas): ni sus otras empresas ni modo system aunque el titular sea
    superusuario. La pagina publica solo ve y escribe datos de esa empresa."""
    from app.db import rls_context

    if rls_context.is_postgres(db):
        uid = rls_context.public_site_user_id_by_slug(db, slug)
        if uid is None:
            return None
        return rls_context.bind_user_single_company(db, uid)
    return db.query(User).filter(
        User.public_site_slug == slug,
        User.public_site_enabled == True,
        User.is_active == True,
    ).first()


@router.get("/{slug}/info", response_model=PublicSiteInfoResponse)
def get_public_site_info(slug: str, db: Session = Depends(get_db)):
    """Info pública del negocio. 404 si slug no existe o web desactivada."""
    user = _get_user_by_slug(db, slug)
    if not user:
        raise HTTPException(status_code=404, detail="Web no disponible")
    name = (user.company_name or user.full_name or user.email or "Negocio").strip()
    # Reservas habilitadas si tiene web pública activa (y en el futuro podríamos un flag aparte)
    reservations_enabled = True
    return PublicSiteInfoResponse(name=name, reservations_enabled=reservations_enabled)


def _env_limit(name: str, default: int) -> int:
    import os

    try:
        v = int((os.getenv(name) or "").strip() or default)
        return v if v > 0 else default
    except ValueError:
        return default


def _enforce_reservation_limits(db: Session, user: User, guest_phone: str) -> None:
    """Limites reales en BD contra abuso del formulario publico (no hay captcha)."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    per_slug = _env_limit("RESERVATION_LIMIT_PER_SLUG_PER_HOUR", 30)
    n_slug = (
        db.query(Reservation)
        .filter(Reservation.user_id == user.id, Reservation.source == "web",
                Reservation.created_at >= now - timedelta(hours=1))
        .count()
    )
    if n_slug >= per_slug:
        logger.warning("reserva publica limitada por slug user_id=%s n=%s", user.id, n_slug)
        raise HTTPException(status_code=429, detail="Demasiadas reservas en poco tiempo. Prueba mas tarde.")
    per_phone = _env_limit("RESERVATION_LIMIT_PER_PHONE_PER_DAY", 5)
    n_phone = (
        db.query(Reservation)
        .filter(Reservation.user_id == user.id, Reservation.source == "web",
                Reservation.guest_phone == guest_phone,
                Reservation.created_at >= now - timedelta(days=1))
        .count()
    )
    if n_phone >= per_phone:
        logger.warning("reserva publica limitada por telefono user_id=%s n=%s", user.id, n_phone)
        raise HTTPException(status_code=429, detail="Demasiadas reservas con este telefono hoy.")


async def _confirm_by_whatsapp(db: Session, r: Reservation, body: "CreateReservationRequest", business_name: str) -> str:
    """Confirmacion por WhatsApp SOLO con consentimiento. Devuelve el resultado (sin simular)."""
    from datetime import timedelta

    import services.outbound_consent_v1 as consent_svc
    from services.whatsapp_service import whatsapp_service

    if not body.whatsapp_consent:
        return "no_consent"
    if not whatsapp_service.is_configured():
        return "not_configured"
    phone = consent_svc.normalize_phone(body.guest_phone)
    if not phone:
        logger.warning("Reserva %s: telefono no valido para WhatsApp", r.id)
        return "invalid_phone"

    def _record(status_value: str, detail: Optional[str] = None) -> None:
        consent_svc.record_outbound(
            db, company_id=r.company_id, user_id=r.user_id, channel=consent_svc.CHANNEL_WHATSAPP,
            purpose="reservation_confirmation", recipient=phone, status_value=status_value, detail=detail,
            recipient_kind="guest", recipient_ref_id=r.id,
        )

    per_phone = _env_limit("PUBLIC_WHATSAPP_LIMIT_PER_PHONE_PER_DAY", 3)
    # Limite anti-abuso GLOBAL por telefono (todas las empresas): con RLS se cuenta con la funcion
    # acotada outbound_recent_count() (0071: solo devuelve un numero), ver count_recent_all_companies.
    used = consent_svc.count_recent_all_companies(
        db, window=timedelta(days=1), channel=consent_svc.CHANNEL_WHATSAPP,
        purpose="reservation_confirmation", recipient=phone,
    )
    if used >= per_phone:
        _record("blocked", "limite diario de confirmaciones a este telefono")
        return "rate_limited"
    msg = (
        f"Hola {body.guest_name.strip()}, tu reserva en *{business_name}* "
        f"para el {body.reservation_date} a las {body.reservation_time.strip()} "
        f"({body.num_guests} comensales) ha sido recibida. Te confirmaremos pronto."
    )
    try:
        result = await whatsapp_service.send_message(phone, msg)
    except Exception as exc:
        logger.exception("Reserva %s: error enviando WhatsApp", r.id)
        result = {"success": False, "error": type(exc).__name__}
    if result.get("success"):
        _record("sent")
        return "sent"
    _record("failed", str(result.get("error") or "error del proveedor"))
    logger.warning("Reserva %s creada pero WhatsApp no enviado", r.id)
    return "failed"


@router.post("/{slug}/reservations")
async def create_reservation(slug: str, body: CreateReservationRequest, db: Session = Depends(get_db)):
    """Crear reserva desde la web publica. Confirmacion por WhatsApp solo si el cliente marco la
    casilla de consentimiento y Twilio esta configurado. Limites por slug y por telefono."""
    from datetime import datetime, timezone

    user = _get_user_by_slug(db, slug)
    if not user:
        raise HTTPException(status_code=404, detail="Web no disponible")
    try:
        res_date = date.fromisoformat(body.reservation_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido (use YYYY-MM-DD)")
    if body.num_guests < 1 or body.num_guests > 50:
        raise HTTPException(status_code=400, detail="Número de comensales no válido")
    guest_phone = body.guest_phone.strip()
    if not guest_phone:
        raise HTTPException(status_code=400, detail="Teléfono obligatorio")
    _enforce_reservation_limits(db, user, guest_phone)
    r = Reservation(
        user_id=user.id,
        company_id=primary_company_id(db, user),
        guest_name=body.guest_name.strip(),
        guest_phone=guest_phone,
        guest_email=body.guest_email.strip() if body.guest_email else None,
        reservation_date=res_date,
        reservation_time=body.reservation_time.strip(),
        num_guests=body.num_guests,
        notes=body.notes[:500] if body.notes else None,
        status="pending",
        source="web",
        whatsapp_consent=bool(body.whatsapp_consent),
        whatsapp_consent_at=datetime.now(timezone.utc) if body.whatsapp_consent else None,
    )
    db.add(r)
    db.commit()
    db.refresh(r)

    business_name = (user.company_name or user.full_name or user.email or "el establecimiento").strip()
    whatsapp = await _confirm_by_whatsapp(db, r, body, business_name)
    logger.info(
        "reserva publica id=%s company_id=%s whatsapp_consent=%s whatsapp=%s",
        r.id, r.company_id, bool(body.whatsapp_consent), whatsapp,
    )
    return {
        "success": True,
        "id": r.id,
        "message": "Reserva recibida. Te confirmaremos pronto.",
        "whatsapp_confirmation": whatsapp,
    }
