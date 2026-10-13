"""QR de fichaje del centro de trabajo, firmado por ZEUS y ligado a una empresa.

Antes el metodo QR aceptaba cualquier cadena no vacia y la UI fabricaba el token
(`ui-<empleado>-<timestamp>`): un "fichaje por QR" sin ningun QR. Ahora:
- El dueno obtiene el QR de su empresa (GET /api/v1/checkin/qr-token) y lo imprime/
  muestra en el centro de trabajo.
- Al fichar con method=qr el token debe ser el de ESA empresa (HMAC con SECRET_KEY);
  un token inventado o de otra empresa se rechaza con 403.
Formato: ZEUSQR1.<company_id>.<firma hex 32>. No caduca (QR impreso); para rotarlo
hay que cambiar SECRET_KEY (pendiente: rotacion por empresa).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Optional

from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

_PREFIX = "ZEUSQR1"


def _sig(company_id: int) -> str:
    key = (settings.SECRET_KEY or "").encode("utf-8")
    msg = f"zeus-checkin-qr|{int(company_id)}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:32]


def issue_company_qr_token(company_id: int) -> str:
    return f"{_PREFIX}.{int(company_id)}.{_sig(company_id)}"


def verify_company_qr_token(token: Optional[str], company_id: int, *, user_id: Optional[int] = None) -> None:
    raw = str(token or "").strip()
    parts = raw.split(".")
    ok = (
        len(parts) == 3
        and parts[0] == _PREFIX
        and parts[1].isdigit()
        and int(parts[1]) == int(company_id)
        and hmac.compare_digest(parts[2], _sig(company_id))
    )
    if not ok:
        logger.warning("fichaje QR rechazado: token no valido para company_id=%s user_id=%s", company_id, user_id)
        raise HTTPException(status_code=403, detail="Código QR no válido para esta empresa.")
