"""Gastos deducibles para modelo 303 (IVA soportado)."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    issue_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    base_amount = Column(Float(precision=2), nullable=False, default=0.0)
    tax_amount = Column(Float(precision=2), nullable=False, default=0.0)
    tax_rate = Column(Float(precision=4), nullable=False, default=21.0)
    category = Column(String(100), nullable=True)
    invoice_ref = Column(String(100), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company", foreign_keys=[company_id])
