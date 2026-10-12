"""Bloqueo legal del fichaje biometrico (reconocimiento facial, huella...).

El registro de jornada con datos biometricos es tratamiento de categoria especial
(art. 9 RGPD) y la AEPD (Guia sobre tratamientos de control de presencia mediante
sistemas biometricos, nov. 2023) lo considera, por regla general, no necesario ni
proporcional para el control horario. ZEUS no dispone de evaluacion de impacto ni de
base legal para ello, asi que NO procesa ninguna cara ni guarda plantillas: cualquier
peticion de fichaje biometrico se rechaza con 501 y motivo explicito, y se registra.

Antes la UI mapeaba el metodo "Facial" a "device" y fichaba igualmente, sin ninguna
cara: un fichaje "facial" que no lo era.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

BIOMETRIC_METHODS = frozenset({"face", "facial", "biometric", "biometrico", "fingerprint", "huella"})

BIOMETRIC_BLOCK_REASON = (
    "Fichaje biometrico (reconocimiento facial/huella) bloqueado: es un tratamiento de datos "
    "de categoria especial (art. 9 RGPD) que la AEPD no considera proporcional para el control "
    "horario. ZEUS no procesa caras ni guarda plantillas. Usa PIN, QR del centro, "
    "geolocalizacion o registro manual."
)


def is_biometric_method(method: Optional[str]) -> bool:
    return str(method or "").strip().lower() in BIOMETRIC_METHODS


def reject_biometric(method: Optional[str], *, user_id: Optional[int], company_id: Optional[int]) -> None:
    """Lanza 501 si el metodo es biometrico (y deja log del intento)."""
    if not is_biometric_method(method):
        return
    logger.warning(
        "fichaje biometrico rechazado (bloqueo legal) method=%s user_id=%s company_id=%s",
        method, user_id, company_id,
    )
    raise HTTPException(
        status_code=501,
        detail=BIOMETRIC_BLOCK_REASON,
        headers={"X-Zeus-Block": "biometric_checkin_blocked"},
    )
