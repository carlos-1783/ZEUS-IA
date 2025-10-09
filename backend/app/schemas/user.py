from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Union
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)

class UserUpdate(UserBase):
    password: Optional[str] = Field(None, min_length=8, max_length=100)

class UserInDBBase(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class User(UserInDBBase):
    pass

class UserInDB(UserInDBBase):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    user_id: Optional[int] = None

class TokenPayload(BaseModel):
    sub: Union[str, int, None] = None  # Email del usuario
    user_id: Optional[int] = None      # ID del usuario
    type: Optional[str] = None         # Tipo de token (access/refresh)
    exp: Optional[datetime] = None     # Fecha de expiración
    iat: Optional[datetime] = None     # Fecha de emisión
    
    class Config:
        json_encoders = {
            datetime: lambda v: int(v.timestamp()) if v else None
        }
    
    @validator('sub', pre=True)
    def validate_sub(cls, v):
        # Asegurar que el subject sea un string (email) o un entero (ID)
        if v is not None and not isinstance(v, (str, int)):
            raise ValueError("El campo 'sub' debe ser un string (email) o un entero (ID)")
        return v
    
    @validator('type')
    def validate_token_type(cls, v):
        if v not in ['access', 'refresh']:
            raise ValueError("El tipo de token debe ser 'access' o 'refresh'")
        return v
