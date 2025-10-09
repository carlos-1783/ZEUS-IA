"""
Wrapper para compatibilidad con código existente que usa jwt_handler.
Toda la lógica de JWT se ha movido a security.py para evitar duplicidades.
"""
from typing import Any, Dict

from fastapi import HTTPException, status
from jose import JWTError

from app.core.security import (
    create_access_token as _create_access_token,
    create_refresh_token as _create_refresh_token,
    get_current_user,
    oauth2_scheme,
    SECRET_KEY,
    settings
)

# Re-exportar para compatibilidad
JWTTokenError = JWTError

def create_access_token(data: dict, expires_minutes: int = None) -> str:
    """
    Wrapper para mantener compatibilidad con código existente.
    Delega en security.create_access_token
    """
    return _create_access_token(data, expires_minutes)

def verify_token(token: str) -> dict:
    """
    Wrapper para mantener compatibilidad con código existente.
    Delega en security.get_current_user
    """
    from app.db.session import SessionLocal
    
    db = SessionLocal()
    try:
        user = get_current_user(db, token)
        return {
            "sub": user.email,
            "email": user.email,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser
        }
    except HTTPException as e:
        if e.status_code == status.HTTP_401_UNAUTHORIZED:
            raise JWTTokenError("Token inválido o expirado")
        raise JWTError(str(e))
    except Exception as e:
        raise JWTError(f"Error al verificar el token: {str(e)}")
    finally:
        db.close()

def create_refresh_token(data: dict) -> str:
    """
    Wrapper para mantener compatibilidad con código existente.
    Delega en security.create_refresh_token
    """
    return _create_refresh_token()

# Re-exportar constantes para compatibilidad
ISSUER = settings.JWT_ISSUER
AUDIENCE = settings.JWT_AUDIENCE
ALGORITHM = settings.ALGORITHM

# Este archivo mantiene compatibilidad con código existente, pero se recomienda
# actualizar el código para usar directamente las funciones de security.py
