"""
stripe_readiness_check: comprobacion REAL de la configuracion de Stripe.

Fase 2 / Step 2: antes iba al handler generico, que copiaba el payload y marcaba la tarea
como "executed_internal" sin comprobar nada. Ahora lee la configuracion real del servicio
(sin llamadas externas: lo declara con check_type=configured_only).
"""

from __future__ import annotations

from typing import Any, Dict

from app.models.agent_activity import AgentActivity

HANDLER_NAME = "STRIPE_READINESS_CHECK"


def handle_stripe_readiness_check(activity: AgentActivity) -> Dict[str, Any]:
    from services.stripe_service import stripe_service

    status = stripe_service.get_status()
    missing = [
        name
        for name, ok in (("STRIPE_API_KEY", status.get("configured")), ("STRIPE_WEBHOOK_SECRET", status.get("webhooks_enabled")))
        if not ok
    ]
    ready = not missing
    note = (
        f"Stripe listo (modo {status.get('detected_mode')})."
        if ready
        else "Stripe NO listo: falta " + ", ".join(missing) + "."
    )
    return {
        "status": "completed" if ready else "failed",
        "details_update": {
            "real_execution": True,
            "check_type": "configured_only",
            "stripe": status,
            "missing": missing,
            "ready": ready,
        },
        "notes": note,
        "executed_handler": HANDLER_NAME,
    }
