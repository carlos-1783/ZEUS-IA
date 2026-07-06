"""ZEUS integrations E2E — real API probes without charges or outbound messages."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.email_service import email_service
from services.stripe_service import stripe_service
from services.whatsapp_service import whatsapp_service
from services.zeus_core_orchestrator_v1 import check_core_orchestration_env
from services.zeus_phase_b_test_v1 import check_phase_b_env
from services.zeus_phase_c_test_v1 import check_phase_c_env

logger = logging.getLogger(__name__)

_PROBE_TIMEOUT = 15


def _check(
    *,
    check_id: str,
    name: str,
    configured: bool,
    reachable: bool,
    ok: bool,
    detail: str,
    provider: str = "",
    probe: str = "free",
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": check_id,
        "name": name,
        "provider": provider,
        "configured": configured,
        "reachable": reachable,
        "ok": ok,
        "detail": detail,
        "probe": probe,
        "error": error,
    }


def _probe_stripe_sync() -> Dict[str, Any]:
    status = stripe_service.get_status()
    if not status.get("configured"):
        return _check(
            check_id="stripe",
            name="Stripe (pagos)",
            provider="Stripe",
            configured=False,
            reachable=False,
            ok=False,
            detail="STRIPE_API_KEY no configurada en Railway",
            error="not_configured",
        )
    try:
        import stripe  # pyright: ignore[reportMissingImports]

        account = stripe.Account.retrieve()
        mode = status.get("detected_mode") or "unknown"
        webhook = "sí" if status.get("webhooks_enabled") else "no"
        return _check(
            check_id="stripe",
            name="Stripe (pagos)",
            provider="Stripe",
            configured=True,
            reachable=True,
            ok=True,
            detail=f"Cuenta {account.id} · modo {mode} · webhook {webhook}",
            probe="Account.retrieve (sin cargo)",
        )
    except Exception as exc:
        logger.warning("Stripe E2E probe failed: %s", exc)
        return _check(
            check_id="stripe",
            name="Stripe (pagos)",
            provider="Stripe",
            configured=True,
            reachable=False,
            ok=False,
            detail="API key presente pero Stripe rechazó la conexión",
            error=str(exc),
        )


def _probe_twilio_sync() -> Dict[str, Any]:
    status = whatsapp_service.get_status()
    if not status.get("configured"):
        enabled = status.get("enabled", True)
        reason = "TWILIO_WHATSAPP_ENABLED=false" if enabled is False else "credenciales Twilio ausentes"
        return _check(
            check_id="whatsapp",
            name="WhatsApp (Twilio)",
            provider="Twilio",
            configured=False,
            reachable=False,
            ok=False,
            detail=reason,
            error="not_configured",
        )
    try:
        client = whatsapp_service.client
        sid = whatsapp_service.account_sid
        account = client.api.accounts(sid).fetch()
        number = status.get("whatsapp_number") or "—"
        return _check(
            check_id="whatsapp",
            name="WhatsApp (Twilio)",
            provider="Twilio",
            configured=True,
            reachable=True,
            ok=True,
            detail=f"Cuenta {account.friendly_name} ({account.status}) · from {number}",
            probe="Account.fetch (sin enviar mensaje)",
        )
    except Exception as exc:
        logger.warning("Twilio E2E probe failed: %s", exc)
        return _check(
            check_id="whatsapp",
            name="WhatsApp (Twilio)",
            provider="Twilio",
            configured=True,
            reachable=False,
            ok=False,
            detail="Credenciales presentes pero Twilio rechazó la conexión",
            error=str(exc),
        )


def _probe_sendgrid_sync() -> Dict[str, Any]:
    api_key = email_service.api_key
    if not api_key:
        if email_service.is_resend_configured():
            return _probe_resend_sync()
        if email_service.is_smtp_configured():
            return _probe_smtp_sync()
        return _check(
            check_id="email",
            name="Email (SendGrid)",
            provider="SendGrid",
            configured=False,
            reachable=False,
            ok=False,
            detail="SENDGRID_API_KEY no configurada",
            error="not_configured",
        )
    try:
        resp = requests.get(
            "https://api.sendgrid.com/v3/scopes",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_PROBE_TIMEOUT,
        )
        if resp.status_code == 200:
            scopes = resp.json().get("scopes") or []
            from_email = email_service.from_email
            return _check(
                check_id="email",
                name="Email (SendGrid)",
                provider="SendGrid",
                configured=True,
                reachable=True,
                ok=True,
                detail=f"API key válida · {len(scopes)} scopes · from {from_email}",
                probe="GET /v3/scopes (sin enviar email)",
            )
        return _check(
            check_id="email",
            name="Email (SendGrid)",
            provider="SendGrid",
            configured=True,
            reachable=False,
            ok=False,
            detail=f"SendGrid respondió HTTP {resp.status_code}",
            error=resp.text[:200] if resp.text else f"http_{resp.status_code}",
        )
    except Exception as exc:
        logger.warning("SendGrid E2E probe failed: %s", exc)
        return _check(
            check_id="email",
            name="Email (SendGrid)",
            provider="SendGrid",
            configured=True,
            reachable=False,
            ok=False,
            detail="No se pudo contactar con SendGrid",
            error=str(exc),
        )


def _probe_resend_sync() -> Dict[str, Any]:
    api_key = email_service.resend_api_key
    from_addr = email_service.resend_from
    try:
        resp = requests.get(
            "https://api.resend.com/domains",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_PROBE_TIMEOUT,
        )
        ok = resp.status_code == 200
        detail = f"Resend API · from {from_addr}"
        if ok:
            domains = resp.json().get("data") or []
            detail = f"Resend OK · {len(domains)} dominio(s) · from {from_addr}"
        return _check(
            check_id="email",
            name="Email (Resend)",
            provider="Resend",
            configured=True,
            reachable=ok,
            ok=ok,
            detail=detail if ok else f"Resend HTTP {resp.status_code}",
            probe="GET /domains (sin enviar email)",
            error=None if ok else (resp.text[:200] or f"http_{resp.status_code}"),
        )
    except Exception as exc:
        return _check(
            check_id="email",
            name="Email (Resend)",
            provider="Resend",
            configured=True,
            reachable=False,
            ok=False,
            detail="No se pudo contactar con Resend",
            error=str(exc),
        )


def _probe_smtp_sync() -> Dict[str, Any]:
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587") or "587")
    user = os.getenv("SMTP_USER", "")
    try:
        import smtplib

        with smtplib.SMTP(host, port, timeout=_PROBE_TIMEOUT) as smtp:
            smtp.ehlo()
            if port == 587:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(user, os.getenv("SMTP_PASSWORD", ""))
        return _check(
            check_id="email",
            name="Email (SMTP)",
            provider="SMTP",
            configured=True,
            reachable=True,
            ok=True,
            detail=f"Login SMTP OK · {host}:{port} · {user}",
            probe="SMTP login (sin enviar email)",
        )
    except Exception as exc:
        return _check(
            check_id="email",
            name="Email (SMTP)",
            provider="SMTP",
            configured=True,
            reachable=False,
            ok=False,
            detail="SMTP configurado pero login falló",
            error=str(exc),
        )


def _probe_openai_sync() -> Dict[str, Any]:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key or api_key == "your-api-key-here":
        return _check(
            check_id="openai",
            name="OpenAI (agentes IA)",
            provider="OpenAI",
            configured=False,
            reachable=False,
            ok=False,
            detail="OPENAI_API_KEY no configurada",
            error="not_configured",
        )
    try:
        resp = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_PROBE_TIMEOUT,
        )
        if resp.status_code == 200:
            return _check(
                check_id="openai",
                name="OpenAI (agentes IA)",
                provider="OpenAI",
                configured=True,
                reachable=True,
                ok=True,
                detail="API key válida · modelos accesibles",
                probe="GET /v1/models (sin generar chat)",
            )
        return _check(
            check_id="openai",
            name="OpenAI (agentes IA)",
            provider="OpenAI",
            configured=True,
            reachable=False,
            ok=False,
            detail=f"OpenAI respondió HTTP {resp.status_code}",
            error=resp.text[:200] if resp.text else f"http_{resp.status_code}",
        )
    except Exception as exc:
        return _check(
            check_id="openai",
            name="OpenAI (agentes IA)",
            provider="OpenAI",
            configured=True,
            reachable=False,
            ok=False,
            detail="No se pudo contactar con OpenAI",
            error=str(exc),
        )


def _probe_database_sync(db: Session) -> Dict[str, Any]:
    try:
        db.execute(text("SELECT 1"))
        return _check(
            check_id="database",
            name="PostgreSQL",
            provider="Railway",
            configured=True,
            reachable=True,
            ok=True,
            detail="SELECT 1 OK",
            probe="db ping",
        )
    except Exception as exc:
        return _check(
            check_id="database",
            name="PostgreSQL",
            provider="Railway",
            configured=True,
            reachable=False,
            ok=False,
            detail="Base de datos no responde",
            error=str(exc),
        )


def _probe_internal_flags() -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for env_fn, check_id, label in (
        (check_phase_b_env, "phase_b", "Automatización Phase B"),
        (check_phase_c_env, "phase_c", "CRM payment risk Phase C"),
        (check_core_orchestration_env, "zeus_core", "ZEUS CORE orquestación"),
    ):
        payload = env_fn()
        all_ok = bool(payload.get("all_ok"))
        checks.append(
            _check(
                check_id=check_id,
                name=label,
                provider="ZEUS",
                configured=True,
                reachable=all_ok,
                ok=all_ok,
                detail="Flags ON" if all_ok else "Faltan flags Railway",
                probe="env flags",
                error=None if all_ok else "flags_incomplete",
            )
        )
    bus_on = (os.getenv("ZEUS_EVENT_BUS_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")
    checks.append(
        _check(
            check_id="event_bus",
            name="Event bus",
            provider="ZEUS",
            configured=bus_on,
            reachable=bus_on,
            ok=bus_on,
            detail="ZEUS_EVENT_BUS_ENABLED=ON" if bus_on else "Event bus desactivado",
            probe="env flag",
            error=None if bus_on else "not_enabled",
        )
    )
    return checks


def _recommendation(checks: List[Dict[str, Any]]) -> str:
    failed_external = [
        c for c in checks
        if c["id"] in ("stripe", "email", "whatsapp", "openai") and not c["ok"]
    ]
    if not failed_external:
        return (
            "Integraciones externas verificadas con API real (sin cargos ni mensajes). "
            "Puedes activar planes de pago con confianza; revisa webhooks en Stripe/Twilio/SendGrid."
        )
    names = ", ".join(c.get("name", c.get("id", "unknown")) for c in failed_external)
    not_configured = [c for c in failed_external if c.get("error") == "not_configured"]
    if len(not_configured) == len(failed_external):
        return (
            f"Pendiente configurar en Railway antes de pagar: {names}. "
            "WhatsApp ya funciona en tu prueba manual; ejecuta este test tras añadir cada API key."
        )
    return (
        f"Revisar credenciales o límites de: {names}. "
        "La variable existe pero la API externa no respondió OK."
    )


async def run_integrations_e2e(db: Session) -> Dict[str, Any]:
    """Run all integration probes (no payments, no outbound email/WhatsApp)."""
    external = await asyncio.gather(
        asyncio.to_thread(_probe_stripe_sync),
        asyncio.to_thread(_probe_twilio_sync),
        asyncio.to_thread(_probe_sendgrid_sync),
        asyncio.to_thread(_probe_openai_sync),
    )
    internal = [_probe_database_sync(db), *_probe_internal_flags()]
    checks: List[Dict[str, Any]] = list(external) + internal
    passed = sum(1 for c in checks if c["ok"])
    failed = len(checks) - passed
    external_ok = all(c["ok"] for c in checks if c["id"] in ("stripe", "email", "whatsapp"))
    return {
        "success": failed == 0,
        "external_ready": external_ok,
        "summary": {"passed": passed, "failed": failed, "total": len(checks)},
        "checks": checks,
        "recommendation": _recommendation(checks),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": (
            "Prueba sin cargo: no crea pagos, no envía emails ni WhatsApp. "
            "Confirma API keys y conectividad. Webhooks inbound requieren prueba manual aparte."
        ),
    }
