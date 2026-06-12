"""Fichajes zeus_time_cost_engine_v1 (auditoría legal + coste laboral)."""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class TimeCostCheckin(Base):
    __tablename__ = "time_cost_checkins"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(String(100), nullable=False, index=True)
    company_employee_id = Column(Integer, ForeignKey("company_employees.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    type = Column(String(32), nullable=False, index=True)  # entrada|salida|pausa_inicio|pausa_fin
    method = Column(String(32), nullable=False)  # qr|pin|geo|device
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    time_tracking_record_id = Column(Integer, ForeignKey("time_tracking_records.id", ondelete="SET NULL"), nullable=True)
    work_session_id = Column(Integer, ForeignKey("employee_work_sessions.id", ondelete="SET NULL"), nullable=True)
    metadata_json = Column(Text, nullable=True)
    client_ip = Column(String(64), nullable=True)
    device_id = Column(String(128), nullable=True)
    user_agent = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
