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
    # Antes se llamaba "company_id" pero apuntaba a users.id (el usuario
    # owner/empleador), no a companies.id — naming engañoso detectado en la
    # auditoría feature/auditoria-real-nucleo. Este proyecto modela "empresa"
    # como el propio User owner (diseño previo al modelo Company/UserCompany
    # multi-tenant; confirmado en services/payroll_assistant_service.py y
    # services/automation/handlers/zeus_payroll_draft.py, que resuelven este
    # valor con `user.id`, nunca con un Company.id real). Se renombra a
    # owner_user_id para reflejar lo que realmente es: mantiene el mismo
    # apuntado a users.id.
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
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
        return f"<PayrollDraft id={self.id} owner_user={self.owner_user_id} employee={self.employee_id} month={self.month}/{self.year}>"
