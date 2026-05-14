from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime

class Customer(Base):
    """Customer model for CRM functionality"""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    email = Column(String(100), unique=False, index=True, nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    tax_id = Column(String(50), nullable=True, index=True)
    notes = Column(Text, nullable=True)

    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Status flags
    is_active = Column(Boolean, default=True)
    is_company = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contacts = relationship("ContactPerson", back_populates="customer", cascade="all, delete-orphan")
    # invoices = relationship("Invoice", back_populates="customer")  # TEMPORALMENTE COMENTADO PARA EVITAR ERROR DE IMPORTACIÓN CIRCULAR
    
    # Metadata
    metadata_ = Column("metadata", JSON, nullable=True)


class ContactPerson(Base):
    """Contact person model for customer contacts"""
    __tablename__ = "customer_contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    
    # Contact details
    name = Column(String(100), nullable=False)
    position = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    mobile = Column(String(20), nullable=True)
    
    # Status
    is_primary = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="contacts")
