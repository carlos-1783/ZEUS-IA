"""Cierre de caja del TPV (arqueo) persistido por empresa.

Fase 2 / vertical hosteleria: el cierre anterior no tocaba la BD (expected_cash = initial_cash,
sin sumar ventas) y no se guardaba. Cada cierre registra el periodo cubierto, los totales
reales de `tpv_sales` de la empresa en ese periodo y el descuadre contado.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.sql import func

from app.db.base import Base


class TPVCashClosure(Base):
    __tablename__ = "tpv_cash_closures"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    terminal_id = Column(String(100), nullable=False)
    employee_code = Column(String(100), nullable=True)

    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)

    sales_count = Column(Integer, nullable=False, default=0)
    cash_sales_total = Column(Numeric(12, 2), nullable=False, default=0)
    card_sales_total = Column(Numeric(12, 2), nullable=False, default=0)
    other_sales_total = Column(Numeric(12, 2), nullable=False, default=0)
    sales_total = Column(Numeric(12, 2), nullable=False, default=0)

    initial_cash = Column(Numeric(12, 2), nullable=False)
    final_cash = Column(Numeric(12, 2), nullable=False)
    expected_cash = Column(Numeric(12, 2), nullable=False)
    difference = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), nullable=False)  # ok | discrepancy

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
