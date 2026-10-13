"""Acceso a las credenciales GLOBALES de plataforma de PERSEO (Meta Ads, Instagram, Google Ads...).

Las variables de entorno FACEBOOK_ACCESS_TOKEN / META_AD_ACCOUNT_ID / INSTAGRAM_* /
GOOGLE_ADS_* / YOUTUBE_* / TIKTOK_* son la cuenta del OPERADOR de la plataforma, no
de ninguna empresa cliente. Hoy no existe un almacén de credenciales por empresa
(``marketing_integrations_v1`` en company.metadata solo guarda account_id/username
declarativos, sin token OAuth), así que:

* superusuario (operador de plataforma) → puede usar la credencial global;
* usuario de empresa → 503 honesto "no conectado para tu empresa", sin llamar a la API.

Así ningún usuario puede gastar en la cuenta publicitaria de la plataforma, publicar
en su Instagram o leer sus insights.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)

_LABELS = {
    "meta_ads": "Meta Ads",
    "meta_insights": "Meta Ads",
    "instagram": "Instagram (Meta)",
    "google_ads": "Google Ads",
    "youtube": "YouTube",
    "tiktok": "TikTok",
}


def require_platform_credential_access(user: Any, integration: str) -> None:
    """Deja pasar solo al superusuario; al resto, 503 'no conectado para tu empresa'."""
    if user is not None and bool(getattr(user, "is_superuser", False)):
        logger.info(
            "PERSEO platform credential: uso de credencial global integration=%s superuser_id=%s",
            integration,
            getattr(user, "id", None),
        )
        return
    label = _LABELS.get(integration, integration)
    logger.warning(
        "PERSEO platform credential: denegado integration=%s user_id=%s (sin credencial propia de empresa)",
        integration,
        getattr(user, "id", None),
    )
    raise HTTPException(
        status_code=503,
        detail={
            "error": f"{integration}_not_connected_for_company",
            "message": (
                f"{label} no conectado para tu empresa. Las credenciales de la plataforma "
                "no se usan en nombre de empresas cliente y aún no hay conexión propia "
                "(OAuth) de tu empresa con este servicio."
            ),
            "integration": integration,
        },
    )


def platform_credential_usable_by(user: Any) -> bool:
    return bool(user is not None and getattr(user, "is_superuser", False))
