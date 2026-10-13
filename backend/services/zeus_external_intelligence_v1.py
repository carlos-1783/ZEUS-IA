"""
Inteligencia externa v1 — sin fuente externa configurada no hay investigacion.

Fase 2 (#14): antes devolvia success=True con todos los campos a "unknown" y, ademas,
SOBRESCRIBIA `crm_leads.external_insights_json` / `customers.metadata_.external_insights` con
ese bloque vacio (borrando lo que hubiera). No existe ninguna API externa de datos de empresas
integrada en el repo, asi que ahora se responde 501 `external_source_not_configured` y no se
escribe nada en BD. Queda registrado en log.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)

EXTERNAL_SOURCE_ERROR = "external_source_not_configured"


def research_business(
    db: Session,
    *,
    user: User,
    query: str,
    lead_id: Optional[int] = None,
    customer_id: Optional[int] = None,
):
    """Sin fuente externa real: 501 honesto, sin tocar CRM."""
    _ = db
    logger.info(
        "intelligence/research no disponible (sin fuente externa): user=%s lead=%s customer=%s",
        getattr(user, "id", None), lead_id, customer_id,
    )
    raise HTTPException(
        status_code=501,
        detail={
            "error": EXTERNAL_SOURCE_ERROR,
            "message": (
                "No hay ninguna fuente externa de datos de empresas configurada: no se ha "
                "investigado nada y no se ha modificado el lead ni el cliente."
            ),
            "query": (query or "").strip(),
            "persisted": False,
        },
    )
