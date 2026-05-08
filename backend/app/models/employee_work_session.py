"""Sesión laboral (jornada) ligada a fichaje y opcionalmente a ventas TPV."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class EmployeeWorkSession(Base):
    """
    Una fila por jornada iniciada en login (empleado).
    Se asocia al TimeTrackingRecord ACTIVE que representa el clock-in de esa jornada.
    """

    __tablename__ = "employee_work_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_code = Column(String(100), nullable=False, index=True)
    time_tracking_record_id = Column(
        Integer,
        ForeignKey("time_tracking_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # active | closed | auto_closed | superseded
    status = Column(String(32), nullable=False, default="active", index=True)
    opened_at = Column(DateTime(timezone=True), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    close_reason = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", foreign_keys=[user_id])
