"""Verificacion de webhooks entrantes (Twilio/WhatsApp y email inbound). Fail-closed.

Cada verificador devuelve None si la peticion es autentica o lanza HTTPException:
  503 -> secreto no configurado en el servidor (nunca se procesa)
  403 -> firma/secreto ausente o invalido
En ambos casos se registra un evento THALOS 'deny' con el motivo.
"""
from __future__ import annotations

import hmac
import logging
from typing import Any, Mapping, Optional

from fastapi import HTTPException, Request, status
from twilio.request_validator import RequestValidator

from app.core.config import settings
from app.db.session import SessionLocal
from services.thalos_request_guard_v1 import record_security_event

logger = logging.getLogger(__name__)

EMAIL_SECRET_HEADER = "x-inbound-secret"
EMAIL_SECRET_QUERY = "secret"


def twilio_public_url(request: Request) -> str:
    """URL exacta que Twilio firmo (la configurada en su consola).

    Prioridad: PUBLIC_BASE_URL + path + query; si no, X-Forwarded-Proto/Host (Railway los
    pone); si no, la URL tal como la ve la app.
    """
    path = request.url.path
    query = request.url.query
    base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    if not base:
        proto = (request.headers.get("x-forwarded-proto") or request.url.scheme).split(",")[0].strip()
        host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc)
        base = f"{proto}://{host.split(',')[0].strip()}"
    return base + path + (f"?{query}" if query else "")


def _deny(request: Request, source: str, reason: str, code: int) -> HTTPException:
    db = SessionLocal()
    try:
        record_security_event(
            db,
            event_type="webhook_signature",
            severity="warning" if code == 403 else "error",
            source=source,
            details={"route": request.url.path, "method": request.method, "decision": "deny", "reason": reason},
            ip_address=request.client.host if request.client else None,
            action_taken="deny",
            decision_rule=reason,
        )
    except Exception:
        logger.exception("No se pudo registrar el evento de webhook denegado")
    finally:
        db.close()
    detail = "Webhook no configurado." if code == 503 else "Firma de webhook invalida."
    return HTTPException(status_code=code, detail=detail)


def verify_twilio_request(request: Request, params: Mapping[str, Any]) -> None:
    token = (getattr(settings, "TWILIO_AUTH_TOKEN", "") or "").strip()
    if not token:
        raise _deny(request, "twilio_signature", "twilio_token_not_configured", status.HTTP_503_SERVICE_UNAVAILABLE)
    signature = request.headers.get("x-twilio-signature", "")
    if not signature:
        raise _deny(request, "twilio_signature", "twilio_signature_missing", status.HTTP_403_FORBIDDEN)
    if not RequestValidator(token).validate(twilio_public_url(request), params, signature):
        raise _deny(request, "twilio_signature", "twilio_signature_invalid", status.HTTP_403_FORBIDDEN)


def verify_email_inbound_secret(request: Request) -> None:
    secret = (getattr(settings, "EMAIL_INBOUND_WEBHOOK_SECRET", "") or "").strip()
    if not secret:
        raise _deny(request, "email_inbound_secret", "email_secret_not_configured", status.HTTP_503_SERVICE_UNAVAILABLE)
    provided: Optional[str] = request.headers.get(EMAIL_SECRET_HEADER) or request.query_params.get(EMAIL_SECRET_QUERY)
    if not provided:
        raise _deny(request, "email_inbound_secret", "email_secret_missing", status.HTTP_403_FORBIDDEN)
    if not hmac.compare_digest(provided.encode("utf-8"), secret.encode("utf-8")):
        raise _deny(request, "email_inbound_secret", "email_secret_invalid", status.HTTP_403_FORBIDDEN)
