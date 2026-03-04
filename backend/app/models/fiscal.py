"""
ZEUS_TPV_FULL_FISCAL_INFRASTRUCTURE_ES_003
Modelos fiscales: tipos de IVA, perfiles fiscales, ventas TPV y líneas con snapshot inmutable.
Preparado para modelo 303, recargo de equivalencia e inspección AEAT.
"""
from sqlalchemy import Column, Integer, String, Numeric, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class TaxRate(Base):
    """Tipos de IVA por usuario (21%, 10%, 4%, exento, etc.) con ámbito de aplicación."""
    __tablename__ = "tax_rates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    rate = Column(Numeric(5, 4), nullable=False)  # 0.21, 0.10, 0.04, 0
    applies_to = Column(String(20), nullable=False)  # product, service, takeaway, onsite
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", backref="tax_rates")


class FiscalProfile(Base):
    """Perfil fiscal del usuario: régimen IVA y recargo de equivalencia."""
    __tablename__ = "fiscal_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    vat_regime = Column(String(30), nullable=False)  # general, recargo_equivalencia, exento
    apply_recargo_equivalencia = Column(Boolean, nullable=False, default=False)
    recargo_rate = Column(Numeric(5, 4), nullable=True)  # ej. 5.2% = 0.052
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", backref="fiscal_profiles")


class TPVSale(Base):
    """Cabecera de venta TPV con totales fiscales (snapshot inmutable, no recalcular)."""
    __tablename__ = "tpv_sales"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket_id = Column(String(100), nullable=False, unique=True, index=True)
    document_type = Column(String(20), nullable=False)  # ticket, factura
    sale_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    payment_method = Column(String(30), nullable=False)
    consumption_type = Column(String(20), nullable=True)  # onsite, takeaway
    subtotal = Column(Numeric(12, 2), nullable=False)
    tax_amount = Column(Numeric(12, 2), nullable=False)
    recargo_amount = Column(Numeric(12, 2), nullable=True)
    total = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", backref="tpv_sales")
    items = relationship("TPVSaleItem", back_populates="sale", cascade="all, delete-orphan")


class TPVSaleItem(Base):
    """Línea de venta TPV con snapshot fiscal por línea (base, IVA, recargo). Inmutable."""
    __tablename__ = "tpv_sale_items"

    id = Column(Integer, primary_key=True, index=True)
    tpv_sale_id = Column(Integer, ForeignKey("tpv_sales.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String(100), nullable=True)
    product_name = Column(String(200), nullable=False)
    quantity = Column(Numeric(12, 4), nullable=False)
    unit_price = Column(Numeric(12, 4), nullable=False)
    tax_rate_snapshot = Column(Numeric(5, 4), nullable=False)
    tax_amount = Column(Numeric(12, 2), nullable=False)
    base_amount = Column(Numeric(12, 2), nullable=False)
    recargo_rate_snapshot = Column(Numeric(5, 4), nullable=True)
    recargo_amount = Column(Numeric(12, 2), nullable=True)
    consumption_type = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sale = relationship("TPVSale", back_populates="items")
