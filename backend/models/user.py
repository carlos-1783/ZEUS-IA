"""
ZEUS-IA - User Model
Modelo de usuarios del sistema
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from backend.models.database import Base


class User(Base):
    """
    Usuario del sistema ZEUS-IA
    Puede ser: admin, manager, viewer, restaurante_owner
    """
    
    __tablename__ = "users"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # Información básica
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(255))
    
    # Autenticación
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    # Roles y permisos
    role = Column(String(50), default="viewer")  # admin, manager, viewer, restaurante_owner
    permissions = Column(JSON, default=dict)  # Permisos específicos
    
    # Organización (para multi-tenant)
    organization_id = Column(String(100), index=True)  # "piloto_restaurante", "cliente_pago_1", etc.
    organization_name = Column(String(255))
    
    # Configuración de notificaciones HITL
    hitl_email = Column(String(255))  # Email para notificaciones HITL
    hitl_phone = Column(String(50))   # Teléfono para notificaciones críticas
    hitl_enabled = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    
    # Configuración personal
    preferences = Column(JSON, default=dict)  # UI preferences, idioma, etc.
    
    def __repr__(self):
        return f"<User {self.username} ({self.role})>"
    
    def to_dict(self):
        """Convierte a diccionario (sin contraseña)"""
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "role": self.role,
            "permissions": self.permissions,
            "organization_id": self.organization_id,
            "organization_name": self.organization_name,
            "hitl_email": self.hitl_email,
            "hitl_enabled": self.hitl_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "preferences": self.preferences,
        }

