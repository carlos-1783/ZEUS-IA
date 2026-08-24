"""
Cifrado simétrico para datos sensibles en reposo (IBAN de cobro, etc.).

Usa Fernet (AES-128-CBC + HMAC-SHA256, autenticado) de la librería
`cryptography`, ya presente en requirements.txt — no es cifrado casero ni
base64 disfrazado de cifrado.

La clave se deriva SIEMPRE de una variable de entorno real
(`FIELD_ENCRYPTION_KEY`). En local/tests (ENVIRONMENT != production), si no
está configurada, se deriva de `SECRET_KEY` (también variable de entorno,
nunca literal en el código) y se registra un aviso — solo para no bloquear
el desarrollo local.

En producción esto NUNCA ocurre: si `FIELD_ENCRYPTION_KEY` no está
configurada, `_resolve_key()` falla en cerrado (`RuntimeError`), sin
importar el estado de `SECRET_KEY`. Cifrado (JWT) y cifrado de datos
sensibles en reposo (IBAN) son dominios de seguridad distintos y nunca deben
compartir clave: si se permitiera el fallback silencioso a SECRET_KEY en
producción, cualquiera con acceso al código fuente podría derivar la misma
clave que usa SECRET_KEY por defecto (ver app/core/config.py) y descifrar
todos los IBANes almacenados sin tocar la BD ni ninguna variable de entorno
real — la misma clase de fallo que causó el incidente de credenciales
hardcodeadas de esta sesión (ver INCIDENTE_SEGURIDAD_CREDENCIALES.md).
"""
import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)

_dev_fallback_notice_logged = False


class EncryptionKeyNotConfiguredError(RuntimeError):
    """FIELD_ENCRYPTION_KEY no configurada en producción: fallo en cerrado."""


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
        # Fallo en cerrado: NUNCA se deriva de SECRET_KEY (otro dominio de
        # seguridad) en producción. Sin FIELD_ENCRYPTION_KEY no hay cifrado
        # posible — se rechaza la operación en vez de cifrar/descifrar con
        # una clave predecible desde el propio código fuente.
        logger.error(
            "[SECURITY] FIELD_ENCRYPTION_KEY no configurada en producción. "
            "Operación de cifrado/descifrado de datos sensibles (IBAN) rechazada. "
            "Configura FIELD_ENCRYPTION_KEY en las variables de entorno de Railway."
        )
        raise EncryptionKeyNotConfiguredError(
            "FIELD_ENCRYPTION_KEY no configurada en producción. No se puede "
            "cifrar ni descifrar datos sensibles (IBAN) sin una clave de "
            "cifrado real e independiente de SECRET_KEY."
        )

    if not _dev_fallback_notice_logged:
        logger.warning(
            "[SECURITY] FIELD_ENCRYPTION_KEY no configurada; usando clave derivada "
            "de SECRET_KEY, válida solo para desarrollo/tests (ENVIRONMENT=%s). "
            "Nunca ocurre en producción: ahí falla en cerrado. "
            "Configura FIELD_ENCRYPTION_KEY en producción.",
            env,
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
