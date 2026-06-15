"""Libro mayor de cashflow — movimientos reales persistidos."""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class CashflowLedgerEntry(Base):
    __tablename__ = "cashflow_ledger"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    invoice_id = Column(Integer, nullable=True, index=True)
    tpv_sale_id = Column(Integer, nullable=True, index=True)
    ticket_id = Column(String(128), nullable=True, index=True)
    amount = Column(Float, nullable=False)
    direction = Column(String(8), nullable=False, default="in")  # in | out
    source = Column(String(64), nullable=False, index=True)
    payment_method = Column(String(64), nullable=True)
    reference = Column(String(255), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
