"""Sesión TPV: operador activo distinto del usuario autenticado (cambiar operador sin logout empresa)."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class TPVOperatorSession(Base):
    """
    Una fila por usuario autenticado: qué empleado RRHH actúa como cobrador en el TPV.
    """

    __tablename__ = "tpv_operator_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_code = Column(String(80), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", backref="tpv_operator_session", uselist=False)
