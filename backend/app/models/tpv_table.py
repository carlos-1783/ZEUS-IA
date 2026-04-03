"""Mesas TPV persistidas por empresa (multi-tenant)."""
from decimal import Decimal

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class TPVTable(Base):
    __tablename__ = "tpv_tables"
    __table_args__ = (UniqueConstraint("company_id", "number", name="uq_tpv_tables_company_number"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    number = Column(Integer, nullable=False)
    name = Column(String(120), nullable=False)
    status = Column(String(50), nullable=False, default="free")
    order_total = Column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    cart_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    company = relationship("Company", backref="tpv_tables")

    def __repr__(self):
        return f"<TPVTable {self.id} company={self.company_id} n={self.number}>"
