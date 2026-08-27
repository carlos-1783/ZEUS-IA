"""
ZEUS_INTERNAL_COMPANY_BOOTSTRAP_002
Modelos Company y UserCompany para empresa interna y vinculación de usuarios.
NO pilot_company, NO modificar SUPERUSER, NO cobros.
"""
from sqlalchemy import Boolean, CheckConstraint, Column, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

# Valores válidos de UserCompany.role. "company_admin"/"member" son los que
# escribe el código de producción (app/, services/); "owner" se añadió tras
# confirmar que 9 suites de tests (tests/test_zeus_*.py, test_afrodita_*,
# test_thalos_*, test_time_cost_engine_v1.py) lo usan de forma consistente
# como valor real al crear UserCompany en sus fixtures — no es un typo
# aislado, así que se trata como valor válido en vez de romper esos tests.
USER_COMPANY_ROLE_VALUES = ("company_admin", "member", "owner")


class Company(Base):
    """Empresa: interna (ZEUS INTERNAL) o cliente. pilot_company=False para interna."""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    pilot_company = Column(Boolean(), default=False, nullable=False)
    status = Column(String(50), default="active", nullable=False)  # active, suspended, etc.
    sector = Column(String(100), nullable=True)
    company_type = Column(String(32), nullable=True, index=True)  # bar_restaurant | office
    country = Column(String(10), nullable=True)
    currency = Column(String(10), default="EUR", nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)  # internal_company, purpose, billing_enabled, etc.
    # Datos de facturación (onboarding): CIF/NIF y razón social son datos ya
    # públicos en cualquier factura real, no requieren cifrado. El IBAN es
    # sensible: se guarda cifrado (Fernet, app/core/crypto.py) y nunca en claro.
    tax_id = Column(String(20), nullable=True, index=True)  # CIF/NIF
    legal_name = Column(String(255), nullable=True)  # razón social
    iban_encrypted = Column(Text, nullable=True)  # IBAN cifrado en reposo
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user_companies = relationship("UserCompany", back_populates="company", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Company {self.slug}>"


class UserCompany(Base):
    """Vinculación usuario-empresa con rol. company_admin solo aplica a esta empresa; SUPERUSER es global."""
    __tablename__ = "user_companies"
    __table_args__ = (
        CheckConstraint("role IN ('company_admin', 'member', 'owner')", name="ck_user_companies_role"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False, default="company_admin")  # company_admin, member, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="user_companies")
    company = relationship("Company", back_populates="user_companies")

    def __repr__(self):
        return f"<UserCompany user_id={self.user_id} company_id={self.company_id} role={self.role}>"
