"""
📋 Payroll Draft Model
Borradores de nómina - SIN presentación oficial ni pagos automáticos.
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base


class PayrollDraft(Base):
    """Borrador de nómina - requiere validación por asesor laboral"""
    __tablename__ = "payroll_drafts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    gross_salary = Column(Float, nullable=False)
    irpf_estimated = Column(Float, default=0.0)
    social_security_estimated = Column(Float, default=0.0)
    net_salary_estimated = Column(Float, default=0.0)

    month = Column(String(20), nullable=True)
    year = Column(Integer, nullable=True)
    status = Column(String(50), default="BORRADOR_GENERADO", nullable=False)
    pdf_path = Column(String(500), nullable=True)

    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<PayrollDraft id={self.id} company={self.company_id} employee={self.employee_id} month={self.month}/{self.year}>"
