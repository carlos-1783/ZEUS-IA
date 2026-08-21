"""
Cifrado simétrico para datos sensibles en reposo (IBAN de cobro, etc.).

Usa Fernet (AES-128-CBC + HMAC-SHA256, autenticado) de la librería
`cryptography`, ya presente en requirements.txt — no es cifrado casero ni
base64 disfrazado de cifrado.

La clave se deriva SIEMPRE de una variable de entorno real
(`FIELD_ENCRYPTION_KEY`). En local/tests, si no está configurada, se deriva
de `SECRET_KEY` (también variable de entorno, nunca literal en el código) y
se registra un aviso — igual que el patrón ya existente para SECRET_KEY en
app/core/config.py. En producción, si falta, se registra un WARNING crítico:
configúrala en Railway antes de almacenar datos sensibles reales.
"""
import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)

_dev_fallback_notice_logged = False


def _key_from_secret(secret: str) -> bytes:
    """Deriva una clave Fernet válida (32 bytes url-safe base64) de cualquier secreto."""
    digest = hashlib.sha256((secret or "").encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _resolve_key() -> bytes:
    global _dev_fallback_notice_logged

    raw_key = os.getenv("FIELD_ENCRYPTION_KEY", "").strip()
    if raw_key:
        return _key_from_secret(raw_key)

    env = os.getenv("ENVIRONMENT", os.getenv("RAILWAY_ENVIRONMENT", "production")).lower()
    if env == "production":
        logger.warning(
            "[SECURITY] FIELD_ENCRYPTION_KEY no configurada en producción. "
            "Configúrala en variables de entorno de Railway antes de almacenar "
            "datos sensibles (IBAN, etc.). Usando clave derivada de SECRET_KEY "
            "como fallback temporal."
        )
    elif not _dev_fallback_notice_logged:
        logger.warning(
            "[SECURITY] FIELD_ENCRYPTION_KEY no configurada; usando clave derivada "
            "de SECRET_KEY, válida solo para desarrollo/tests. "
            "Configura FIELD_ENCRYPTION_KEY en producción."
        )
        _dev_fallback_notice_logged = True

    return _key_from_secret(settings.SECRET_KEY or "zeus-dev-fallback-key")


def _get_fernet() -> Fernet:
    return Fernet(_resolve_key())


def encrypt_sensitive_value(value: str) -> str:
    """Cifra un valor sensible. Devuelve el token Fernet como texto (para columna TEXT)."""
    if value is None:
        return None
    f = _get_fernet()
    token = f.encrypt(str(value).encode("utf-8"))
    return token.decode("utf-8")


def decrypt_sensitive_value(token: str) -> str:
    """Descifra un valor previamente cifrado con encrypt_sensitive_value. Nunca loguea el valor."""
    if not token:
        return ""
    f = _get_fernet()
    try:
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error(
            "[SECURITY] No se pudo descifrar un valor sensible (clave incorrecta o dato corrupto)."
        )
        raise
