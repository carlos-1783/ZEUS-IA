import re
from datetime import datetime, timedelta
from typing import Optional, List, Literal, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator, EmailStr, validator

class TokenPayload(BaseModel):
    """
    Modelo para el payload de los tokens JWT.
    Incluye todos los claims estándar requeridos.
    """
    # Claims estándar
    sub: str = Field(..., description="Subject (user ID or email)")
    exp: datetime = Field(..., description="Expiration time (UTC)")
    iat: datetime = Field(..., description="Issued at time (UTC)")
    nbf: datetime = Field(..., description="Not before time (UTC)")
    aud: str = Field(..., description="Audience")
    iss: str = Field(..., description="Issuer")
    type: Literal["access", "refresh"] = Field(..., description="Token type")
    
    # Claims personalizados
    scopes: List[str] = Field(default_factory=list, description="Lista de permisos")
    user_id: Optional[int] = Field(None, description="ID del usuario en la base de datos")
    
    # Configuración de Pydantic
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: int(v.timestamp())  # Convertir datetime a timestamp para JWT
        }
    )
    
    @field_validator('exp', 'iat', 'nbf', mode='before')
    @classmethod
    def ensure_utc(cls, v):
        """Asegura que las fechas estén en UTC"""
        if isinstance(v, datetime):
            return v.replace(tzinfo=None)  # Asumimos que ya está en UTC
        return v

class TokenResponse(BaseModel):
    """
    Modelo para la respuesta de autenticación.
    Incluye el token de acceso y metadatos relacionados.
    """
    access_token: str = Field(..., description="Token JWT para autenticación")
    token_type: str = Field("bearer", description="Tipo de token")
    expires_in: int = Field(..., description="Tiempo de expiración en segundos")
    user_id: int = Field(..., description="ID del usuario autenticado")
    scopes: List[str] = Field(default_factory=list, description="Permisos del usuario")

class TokenData(BaseModel):
    """
    Modelo para los datos del token después de ser validados.
    Se utiliza internamente en la aplicación.
    """
    sub: str
    user_id: int
    scopes: List[str] = []
    exp: datetime
    iat: datetime
    nbf: datetime
    aud: str
    iss: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    email: Optional[str] = None
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: int(v.timestamp()) if v else None
        }
    )


class Token(BaseModel):
    """Modelo para la respuesta de autenticación básica"""
    access_token: str = Field(..., description="Token de acceso JWT")
    token_type: str = Field("bearer", description="Tipo de token")
    refresh_token: Optional[str] = Field(None, description="Token de actualización")
    expires_in: Optional[int] = Field(None, description="Tiempo de expiración en segundos")
    user_id: Optional[int] = Field(None, description="ID del usuario autenticado")
    scopes: List[str] = Field(default_factory=list, description="Lista de permisos del usuario")

class TokenRefresh(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")
    grant_type: str = "refresh_token"

class LoginRequest(BaseModel):
    username: str = Field(..., description="Email del usuario")
    password: str = Field(..., min_length=8, max_length=100)
    grant_type: str = "password"

class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Email del usuario")
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=3, max_length=100)
    role: Optional[str] = "user"

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        if not re.search(r'[A-Z]', v):
            raise ValueError('La contraseña debe contener al menos una letra mayúscula')
        if not re.search(r'[a-z]', v):
            raise ValueError('La contraseña debe contener al menos una letra minúscula')
        if not re.search(r'[0-9]', v):
            raise ValueError('La contraseña debe contener al menos un número')
        return v

class ResetPasswordRequest(BaseModel):
    email: EmailStr

class NewPasswordRequest(BaseModel):
    token: str = Field(..., description="Token de restablecimiento de contraseña")
    new_password: str = Field(..., min_length=8, max_length=100, description="Nueva contraseña")

    @validator('new_password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        if not re.search(r'[A-Z]', v):
            raise ValueError('La contraseña debe contener al menos una letra mayúscula')
        if not re.search(r'[a-z]', v):
            raise ValueError('La contraseña debe contener al menos una letra minúscula')
        if not re.search(r'[0-9]', v):
            raise ValueError('La contraseña debe contener al menos un número')
        if not re.search(r'[^A-Za-z0-9]', v):
            raise ValueError('La contraseña debe contener al menos un carácter especial')
        return v