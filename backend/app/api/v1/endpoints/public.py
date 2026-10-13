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


def _normalize_phone(phone: str, default_country_code: str = "+34") -> str:
    """Normaliza teléfono para Twilio: solo dígitos y +. Si no empieza por +, se añade default_country_code."""
    s = "".join(c for c in phone.strip() if c.isdigit() or c == "+").strip()
    if not s:
        return ""
    if s.startswith("+"):
        return s
    # Quitar leading 0 si el país tiene prefijo (ej. 612345678 → 34612345678)
    if s.startswith("0") and len(s) > 9:
        s = s.lstrip("0")
    return default_country_code + s


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


@router.post("/{slug}/reservations")
async def create_reservation(slug: str, body: CreateReservationRequest, db: Session = Depends(get_db)):
    """Crear reserva desde la web pública y enviar confirmación por WhatsApp si Twilio está configurado."""
    user = _get_user_by_slug(db, slug)
    if not user:
        raise HTTPException(status_code=404, detail="Web no disponible")
    try:
        res_date = date.fromisoformat(body.reservation_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido (use YYYY-MM-DD)")
    if body.num_guests < 1 or body.num_guests > 50:
        raise HTTPException(status_code=400, detail="Número de comensales no válido")
    r = Reservation(
        user_id=user.id,
        company_id=primary_company_id(db, user),
        guest_name=body.guest_name.strip(),
        guest_phone=body.guest_phone.strip(),
        guest_email=body.guest_email.strip() if body.guest_email else None,
        reservation_date=res_date,
        reservation_time=body.reservation_time.strip(),
        num_guests=body.num_guests,
        notes=body.notes[:500] if body.notes else None,
        status="pending",
        source="web",
    )
    db.add(r)
    db.commit()
    db.refresh(r)

    business_name = (user.company_name or user.full_name or user.email or "el establecimiento").strip()
    # Confirmación por WhatsApp al cliente (si el servicio está configurado)
    try:
        from services.whatsapp_service import whatsapp_service
        if whatsapp_service.is_configured():
            phone = _normalize_phone(body.guest_phone)
            if phone:
                msg = (
                    f"Hola {body.guest_name.strip()}, tu reserva en *{business_name}* "
                    f"para el {body.reservation_date} a las {body.reservation_time.strip()} "
                    f"({body.num_guests} comensales) ha sido recibida. Te confirmaremos pronto."
                )
                result = await whatsapp_service.send_message(phone, msg)
                if not result.get("success"):
                    logger.warning("Reserva %s creada pero WhatsApp no enviado: %s", r.id, result.get("error"))
            else:
                logger.warning("Reserva %s creada pero teléfono del cliente no válido para WhatsApp", r.id)
    except Exception as e:
        logger.warning("Reserva %s creada pero error enviando WhatsApp: %s", r.id, e, exc_info=True)

    return {"success": True, "id": r.id, "message": "Reserva recibida. Te confirmaremos pronto."}
