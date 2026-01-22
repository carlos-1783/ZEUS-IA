from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum as PyEnum
from decimal import Decimal
from typing import List, Optional

from app.db.base import Base

class ProductCategory(PyEnum):
    """Product categories for classification"""
    GOODS = "goods"
    SERVICES = "services"
    DIGITAL = "digital"
    SUBSCRIPTION = "subscription"

class ProductStatus(PyEnum):
    """Product status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"

class Product(Base):
    """Product model for ERP system"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Pricing
    price = Column(Float(precision=2), nullable=False)  # Base price
    cost = Column(Float(precision=2), nullable=True)    # Cost price
    tax_rate = Column(Float(precision=4), default=0.0)  # Default tax rate
    
    # Inventory
    track_inventory = Column(Boolean, default=True)
    quantity_on_hand = Column(Float, default=0.0)
    quantity_allocated = Column(Float, default=0.0)
    low_stock_threshold = Column(Float, default=0.0)
    
    # Classification
    category = Column(Enum(ProductCategory), default=ProductCategory.GOODS)
    status = Column(Enum(ProductStatus), default=ProductStatus.ACTIVE)
    
    # Relationships
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    inventory_movements = relationship("InventoryMovement", back_populates="product")
    invoice_items = relationship("InvoiceItem", back_populates="product")
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata_ = Column("metadata", JSON, nullable=True)

class ProductVariant(Base):
    """Product variants (size, color, etc.)"""
    __tablename__ = "product_variants"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    
    # Variant details
    sku = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)  # e.g., "Large", "Red"
    
    # Pricing overrides
    price_override = Column(Float(precision=2), nullable=True)
    cost_override = Column(Float(precision=2), nullable=True)
    
    # Inventory
    quantity_on_hand = Column(Float, default=0.0)
    quantity_allocated = Column(Float, default=0.0)
    
    # Relationships
    product = relationship("Product", back_populates="variants")
    inventory_movements = relationship("InventoryMovement", back_populates="variant")
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class InventoryMovementType(PyEnum):
    """Types of inventory movements"""
    PURCHASE = "purchase"
    SALE = "sale"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"

class InventoryMovement(Base):
    """Tracks inventory movements and stock levels"""
    __tablename__ = "inventory_movements"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # References
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    
    # Movement details
    movement_type = Column(Enum(InventoryMovementType), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_cost = Column(Float(precision=2), nullable=True)
    
    # References
    reference = Column(String(100), nullable=True)  # PO number, RMA number, etc.
    notes = Column(Text, nullable=True)
    
    # Relationships
    product = relationship("Product", back_populates="inventory_movements")
    variant = relationship("ProductVariant", back_populates="inventory_movements")
    invoice = relationship("Invoice", back_populates="inventory_movements")
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

class InvoiceStatus(PyEnum):
    """Invoice status"""
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    VOID = "void"
    OVERDUE = "overdue"

class InvoiceType(PyEnum):
    """Invoice types"""
    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"
    PROFORMA = "proforma"
    ESTIMATE = "estimate"

class Invoice(Base):
    """Invoice model for billing"""
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), unique=True, index=True, nullable=False)
    
    # References
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    
    # Invoice details
    invoice_type = Column(Enum(InvoiceType), default=InvoiceType.INVOICE)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT)
    issue_date = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=True)
    
    # Totals
    subtotal = Column(Float(precision=2), default=0.0)
    tax_amount = Column(Float(precision=2), default=0.0)
    discount_amount = Column(Float(precision=2), default=0.0)
    total = Column(Float(precision=2), default=0.0)
    
    # Payment information
    amount_paid = Column(Float(precision=2), default=0.0)
    amount_due = Column(Float(precision=2), default=0.0)
    
    # Hacienda integration
    electronic_invoice_key = Column(String(50), nullable=True, index=True)
    electronic_invoice_status = Column(String(20), nullable=True)
    
    # Relationships
    # customer = relationship("Customer", back_populates="invoices")  # TEMPORALMENTE COMENTADO PARA EVITAR ERROR DE IMPORTACIÓN CIRCULAR
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")
    inventory_movements = relationship("InventoryMovement", back_populates="invoice")
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)

class InvoiceItem(Base):
    """Line items on an invoice"""
    __tablename__ = "invoice_items"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    
    # Item details
    description = Column(String(500), nullable=False)
    quantity = Column(Float, default=1.0)
    unit_price = Column(Float(precision=2), nullable=False)
    tax_rate = Column(Float(precision=4), default=0.0)
    discount = Column(Float(precision=2), default=0.0)
    
    # Calculated fields
    subtotal = Column(Float(precision=2), default=0.0)
    tax_amount = Column(Float(precision=2), default=0.0)
    total = Column(Float(precision=2), default=0.0)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="items")
    product = relationship("Product", back_populates="invoice_items")
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PaymentMethod(PyEnum):
    """Payment methods"""
    CASH = "cash"
    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    CHECK = "check"
    OTHER = "other"

class PaymentStatus(PyEnum):
    """Payment status"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"

class Payment(Base):
    """Payment records"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    
    # Payment details
    amount = Column(Float(precision=2), nullable=False)
    payment_method = Column(Enum(PaymentMethod), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    transaction_id = Column(String(100), nullable=True)
    
    # References
    reference = Column(String(100), nullable=True)  # Check number, transaction ID, etc.
    notes = Column(Text, nullable=True)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="payments")
    
    # Metadata
    payment_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class TPVProduct(Base):
    """TPV Product model - Multi-tenant products for TPV module"""
    __tablename__ = "tpv_products"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Multi-tenancy
    
    # Product identification
    product_id = Column(String(100), nullable=False, index=True)  # PROD_xxx format
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    
    # Pricing
    price = Column(Float(precision=2), nullable=False)  # Precio base sin IVA
    price_with_iva = Column(Float(precision=2), nullable=False)  # Precio con IVA
    iva_rate = Column(Float(precision=4), default=21.0)  # Tasa IVA (21%, 10%, 4%, 0%)
    
    # Inventory
    stock = Column(Integer, nullable=True)  # Stock disponible (opcional)
    
    # Media
    image = Column(String(500), nullable=True)  # URL de imagen
    icon = Column(String(50), nullable=True)  # Icono predefinido (coffee, food, service, house, default)
    
    # Metadata
    metadata_ = Column("metadata", JSON, nullable=True)  # Metadata adicional
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationship
    user = relationship("User", backref="tpv_products")
    
    def __repr__(self):
        return f"<TPVProduct {self.product_id} - {self.name} (User: {self.user_id})>"
