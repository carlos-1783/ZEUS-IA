"""
Bus de eventos ligero: registro + actividades para trazabilidad (RAFAEL/JUSTICIA en venta, PERSEO en registro).
No bloquea el flujo principal si falla el log.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def emit_sale_created(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: Optional[int],
    ticket_id: Optional[str],
    tpv_sale_id: Optional[int],
    payment_method: Optional[str],
    db: Optional[Session] = None,
) -> None:
    _ = db  # reservado si en el futuro se reutiliza la sesión del request
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "company_id": company_id,
        "ticket_id": ticket_id,
        "tpv_sale_id": tpv_sale_id,
        "payment_method": payment_method,
    }
    logger.info("event sale_created %s", payload)
    try:
        from services.activity_logger import ActivityLogger

        for agent in ("RAFAEL", "JUSTICIA"):
            ActivityLogger.log_activity(
                agent_name=agent,
                action_type="event_sale_created",
                action_description="Evento: venta TPV registrada (snapshot fiscal)",
                details=payload,
                user_email=user_email,
                status="completed",
                priority="normal",
                visible_to_client=True,
            )
    except Exception as e:
        logger.warning("event_sale_created activity log failed: %s", e)


def emit_user_registered(
    *,
    user_id: int,
    user_email: Optional[str],
    company_name: Optional[str],
    db: Optional[Session] = None,
) -> None:
    _ = db
    payload = {"user_id": user_id, "company_name": company_name}
    logger.info("event user_registered %s", payload)
    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name="PERSEO",
            action_type="event_user_registered",
            action_description="Evento: nuevo usuario registrado (activación marketing/onboarding)",
            details=payload,
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
    except Exception as e:
        logger.warning("event_user_registered activity log failed: %s", e)
