"""Detección de intención en mensajes de chat ZEUS Core."""

from __future__ import annotations

import re
from typing import Optional

from app.schemas.zeus_task import ZeusTaskObject

_CONFIRM_RE = re.compile(
    r"^(confirmar|confirmo|sí\s*confirmo|si\s*confirmo|ejecutar|ejecuta|adelante|ok\s*confirmar)\b",
    re.I,
)

_CAMPAIGN_SEND_RE = re.compile(
    r"(crea|crear|lanza|lanzar|genera|generar|haz|hacer|monta|montar|prepara|preparar)"
    r".{0,80}?"
    r"(oferta|descuento|promoci[oó]n|promo|campa[nñ]a)"
    r".{0,120}?"
    r"(envi|mandar|notific|avis|comunic).{0,40}?(cliente|crm|base)",
    re.I | re.DOTALL,
)

_CAMPAIGN_ONLY_RE = re.compile(
    r"(crea|crear|lanza|genera|haz).{0,60}?(oferta|descuento|promoci[oó]n|campa[nñ]a)",
    re.I | re.DOTALL,
)

_SEND_OFFER_RE = re.compile(
    r"^(envi[aá]|mandar?|notific).{0,80}?"
    r"(oferta|descuento|promoci[oó]n|promo|campa[nñ]a).{0,120}?"
    r"(a\s+)?(cliente|crm|base)",
    re.I | re.DOTALL,
)

_LIST_CUSTOMERS_RE = re.compile(
    r"(cu[aá]ntos|cuantos|lista|listar|mostrar|ver|tengo).{0,40}?cliente",
    re.I,
)

_ANALYTICS_RE = re.compile(
    r"(resumen|estad[ií]stica|m[eé]trica|actividad|analytics).{0,50}?"
    r"(agente|sistema|zeus|global|empresa|últim|ultim)",
    re.I,
)

_TPV_TODAY_RE = re.compile(
    r"(venta|tpv|caja|ticket).{0,30}?(hoy|este\s*d[ií]a|de\s*hoy)|"
    r"(qu[eé]|que)\s+ventas?.{0,25}?hoy",
    re.I,
)

_TPV_RE = re.compile(
    r"(venta|tpv|caja|ticket).{0,40}?(resumen|total|cu[aá]nto|cuanto|últim|ultim)",
    re.I,
)

_OPERATIONAL_RE = re.compile(
    r"(envi[aá]|mandar|campa[nñ]a|oferta|descuento|cliente|venta|tpv|caja|turno|"
    r"jornada|fichaje|importar|confirmar|promoci[oó]n)",
    re.I,
)

_SHIFT_RE = re.compile(
    r"(turno|jornada|fichaje|fichar|control\s*horario).{0,40}?"
    r"(activo|estado|abierto|tengo|estoy)",
    re.I,
)

_DISCOUNT_RE = re.compile(r"(\d{1,2})\s*%|descuento\s*(?:de|del)?\s*(\d{1,2})", re.I)


def looks_like_operational(message: str) -> bool:
    text = (message or "").strip()
    return bool(text and _OPERATIONAL_RE.search(text))


def is_confirmation_message(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(_CONFIRM_RE.search(text))


def parse_intent(message: str) -> ZeusTaskObject:
    text = (message or "").strip()
    lower = text.lower()

    if is_confirmation_message(text):
        return ZeusTaskObject(
            intent="confirm_pending",
            action="confirm_pending",
            raw_message=text,
            confidence=0.95,
        )

    if _LIST_CUSTOMERS_RE.search(text):
        return ZeusTaskObject(
            intent="list_customers_summary",
            action="list_customers",
            raw_message=text,
            confidence=0.85,
        )

    if _ANALYTICS_RE.search(text):
        days = _extract_days(text) or 30
        return ZeusTaskObject(
            intent="analytics_summary",
            action="analytics_summary",
            raw_message=text,
            confidence=0.82,
            metadata={"days": days},
        )

    if _TPV_TODAY_RE.search(text):
        return ZeusTaskObject(
            intent="tpv_sales_today",
            action="tpv_sales_summary",
            raw_message=text,
            confidence=0.88,
            metadata={"period": "today", "days": 1},
        )

    if _TPV_RE.search(text):
        days = _extract_days(text) or 7
        return ZeusTaskObject(
            intent="tpv_sales_summary",
            action="tpv_sales_summary",
            raw_message=text,
            confidence=0.82,
            metadata={"days": days},
        )

    if _SHIFT_RE.search(text):
        return ZeusTaskObject(
            intent="shift_status",
            action="shift_status",
            raw_message=text,
            confidence=0.85,
        )

    discount = _extract_discount(text)
    campaign_name = _extract_campaign_name(text, discount)

    if _SEND_OFFER_RE.search(text) or _CAMPAIGN_SEND_RE.search(text):
        return ZeusTaskObject(
            intent="create_campaign_send",
            action="create_campaign",
            discount_percent=discount,
            target="all_customers",
            campaign_name=campaign_name,
            message_template=_default_offer_message(discount),
            requires_confirmation=True,
            raw_message=text,
            confidence=0.9,
        )

    if _CAMPAIGN_ONLY_RE.search(text) and any(
        k in lower for k in ("cliente", "envi", "mandar", "notific", "email", "correo")
    ):
        return ZeusTaskObject(
            intent="create_campaign_send",
            action="create_campaign",
            discount_percent=discount,
            target="all_customers",
            campaign_name=campaign_name,
            message_template=_default_offer_message(discount),
            requires_confirmation=True,
            raw_message=text,
            confidence=0.75,
        )

    return ZeusTaskObject(intent="unknown", raw_message=text, confidence=0.0)


def _extract_days(text: str) -> Optional[int]:
    m = re.search(r"(\d{1,3})\s*d[ií]as?", text, re.I)
    if m:
        try:
            d = int(m.group(1))
            if 1 <= d <= 365:
                return d
        except ValueError:
            pass
    return None


def _extract_discount(text: str) -> Optional[float]:
    m = _DISCOUNT_RE.search(text)
    if not m:
        return None
    for g in m.groups():
        if g:
            try:
                v = float(g)
                if 0 < v <= 100:
                    return v
            except ValueError:
                pass
    return None


def _extract_campaign_name(text: str, discount: Optional[float]) -> str:
    if discount:
        return f"Oferta {int(discount)}% clientes"
    return "Campaña clientes CRM"


def _default_offer_message(discount: Optional[float]) -> str:
    pct = f"{int(discount)}%" if discount else "especial"
    return (
        f"<p>Hola,</p>"
        f"<p>Tenemos una oferta {pct} reservada para ti. "
        f"Contáctanos para activarla antes de que finalice la promoción.</p>"
        f"<p>Saludos,<br/>Tu equipo</p>"
    )
