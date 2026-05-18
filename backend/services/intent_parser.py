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

_LIST_CUSTOMERS_RE = re.compile(
    r"(cu[aá]ntos|cuantos|lista|listar|mostrar|ver|tengo).{0,40}?cliente",
    re.I,
)

_DISCOUNT_RE = re.compile(r"(\d{1,2})\s*%|descuento\s*(?:de|del)?\s*(\d{1,2})", re.I)


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

    discount = _extract_discount(text)
    campaign_name = _extract_campaign_name(text, discount)

    if _CAMPAIGN_SEND_RE.search(text):
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
