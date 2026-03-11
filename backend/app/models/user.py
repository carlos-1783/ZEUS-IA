from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)
    # Rol: owner = dueño (acceso completo, nóminas); employee = empleado (solo TPV + control horario)
    role = Column(String(20), default="owner", nullable=False)  # owner | employee
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Legal-Fiscal Firewall fields
    email_gestor_fiscal = Column(String, nullable=True)
    email_gestor_laboral = Column(String, nullable=True)
    email_asesor_legal = Column(String, nullable=True)
    autoriza_envio_documentos_a_asesores = Column(Boolean(), default=False)
    
    # Company info
    company_name = Column(String, nullable=True)
    employees = Column(Integer, nullable=True)
    plan = Column(String, nullable=True)  # startup, growth, business, enterprise
    
    # Stripe integration
    stripe_customer_id = Column(String, nullable=True, index=True)
    stripe_subscription_id = Column(String, nullable=True)
    
    # TPV Universal - Business Profile
    tpv_business_profile = Column(String, nullable=True, index=True)  # restaurante, bar, tienda_minorista, etc.
    tpv_config = Column(Text, nullable=True)  # JSON config: {"tables_enabled": true, "services_enabled": false, etc.}
    
    # Control Horario - Business Profile
    control_horario_business_profile = Column(String, nullable=True, index=True)  # oficina, restaurante, tienda, externo, etc.
    control_horario_config = Column(Text, nullable=True)  # JSON config: {"strict_check_in": true, "gps_required": false, etc.}

    # Web pública por cliente (Opción B para todos; si no la necesita, public_site_enabled=False)
    public_site_enabled = Column(Boolean(), default=False, nullable=False)
    public_site_slug = Column(String(100), unique=True, nullable=True, index=True)  # URL: /p/{slug}

    # Relación con empresas (UserCompany) - ZEUS_INTERNAL_COMPANY_BOOTSTRAP_002
    user_companies = relationship(
        "UserCompany",
        back_populates="user",
        foreign_keys="UserCompany.user_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User {self.email}>"


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean(), default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    user = relationship("User", back_populates="refresh_tokens")
    
    def __repr__(self):
        return f"<RefreshToken {self.token}>"


class PasswordResetToken(Base):
    """Token de un solo uso para restablecer contraseña. Caduca en 1 hora."""
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    token = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<PasswordResetToken {self.email}>"


# Add relationships to User model
User.refresh_tokens = relationship("RefreshToken", order_by=RefreshToken.id, back_populates="user")
# Document approvals relationship (lazy import to avoid circular dependency)
User.document_approvals = relationship("DocumentApproval", order_by="DocumentApproval.created_at.desc()", back_populates="user")
