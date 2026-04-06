"""Empleados reales por empresa (RRHH / control horario / TPV)."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class CompanyEmployee(Base):
    """
    Fila de empleado ligada a companies.id.
    employee_code es el identificador estable para employee_schedules / fichajes.
    """

    __tablename__ = "company_employees"
    __table_args__ = (
        UniqueConstraint("company_id", "employee_code", name="uq_company_employees_company_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    full_name = Column(String(255), nullable=False)
    role_title = Column(String(100), nullable=True)
    employee_code = Column(String(80), nullable=False, index=True)
    phone = Column(String(32), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    source = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    company = relationship("Company", backref="company_employees")

    def __repr__(self):
        return f"<CompanyEmployee {self.employee_code} company={self.company_id}>"
