"""
Modelos para el módulo de Control Horario
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum
from typing import Optional


class CheckInMethod(str, enum.Enum):
    """Métodos de fichaje disponibles"""
    FACE = "face"  # Reconocimiento facial
    QR = "qr"  # Código QR
    CODE = "code"  # Código manual
    LOCATION = "location"  # Geolocalización/GPS
    REMOTE = "remote"  # Fichaje remoto/virtual


class RecordStatus(str, enum.Enum):
    """Estado de un registro de fichaje"""
    ACTIVE = "active"  # Empleado dentro (check-in sin check-out)
    COMPLETED = "completed"  # Check-in y check-out completos
    IRREGULAR = "irregular"  # Irregularidades detectadas
    PENDING_REVIEW = "pending_review"  # Pendiente de revisión


class TimeTrackingRecord(Base):
    """
    Registro de fichaje de un empleado
    """
    __tablename__ = "time_tracking_records"

    id = Column(Integer, primary_key=True, index=True)
    
    # Empleado
    employee_id = Column(String(100), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)  # Usuario dueño de la empresa
    
    # Fichajes
    check_in_time = Column(DateTime(timezone=True), nullable=False, index=True)
    check_out_time = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Método de fichaje
    check_in_method = Column(SQLEnum(CheckInMethod), default=CheckInMethod.QR, nullable=False)
    check_out_method = Column(SQLEnum(CheckInMethod), nullable=True)
    
    # Ubicación
    check_in_location = Column(String(255), nullable=True)  # Dirección o coordenadas
    check_out_location = Column(String(255), nullable=True)
    check_in_latitude = Column(Float, nullable=True)
    check_in_longitude = Column(Float, nullable=True)
    check_out_latitude = Column(Float, nullable=True)
    check_out_longitude = Column(Float, nullable=True)
    
    # Horas trabajadas
    hours_worked = Column(Float, nullable=True)  # Horas calculadas
    break_duration = Column(Float, default=0.0)  # Duración de pausas en horas
    
    # Estado y validación
    status = Column(SQLEnum(RecordStatus), default=RecordStatus.ACTIVE, index=True, nullable=False)
    irregularities = Column(JSON, nullable=True)  # {"late_check_in": true, "missing_break": true, etc.}
    irregularities_count = Column(Integer, default=0)
    
    # Validaciones
    is_late_check_in = Column(Boolean, default=False)
    is_early_check_out = Column(Boolean, default=False)
    is_missing_break = Column(Boolean, default=False)
    
    # Sincronización con otros módulos
    synced_with_afrodita = Column(Boolean, default=False)
    synced_with_rafael = Column(Boolean, default=False)
    afrodita_sync_date = Column(DateTime(timezone=True), nullable=True)
    rafael_sync_date = Column(DateTime(timezone=True), nullable=True)
    
    # Notas y observaciones
    notes = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)  # Notas del administrador
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    def __repr__(self):
        return f"<TimeTrackingRecord {self.employee_id} {self.check_in_time}>"


class EmployeeSchedule(Base):
    """
    Horario programado de un empleado
    """
    __tablename__ = "employee_schedules"

    id = Column(Integer, primary_key=True, index=True)
    
    # Empleado
    employee_id = Column(String(100), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    
    # Horario
    day_of_week = Column(Integer, nullable=False)  # 0=Lunes, 6=Domingo
    start_time = Column(String(10), nullable=False)  # "09:00"
    end_time = Column(String(10), nullable=False)  # "18:00"
    
    # Tipo de turno
    shift_type = Column(String(50), nullable=True)  # "mañana", "tarde", "noche", "completo"
    location = Column(String(255), nullable=True)  # Ubicación del turno
    
    # Configuración
    break_start = Column(String(10), nullable=True)  # "14:00"
    break_duration = Column(Integer, default=60)  # Duración en minutos
    is_flexible = Column(Boolean, default=False)  # Horario flexible
    
    # Fechas
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    def __repr__(self):
        return f"<EmployeeSchedule {self.employee_id} {self.day_of_week}>"


class AttendanceReport(Base):
    """
    Reportes de asistencia pre-calculados
    """
    __tablename__ = "attendance_reports"

    id = Column(Integer, primary_key=True, index=True)
    
    # Empleado y período
    employee_id = Column(String(100), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    
    # Período del reporte
    period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end = Column(DateTime(timezone=True), nullable=False, index=True)
    period_type = Column(String(20), nullable=False)  # "daily", "weekly", "monthly"
    
    # Métricas
    total_hours = Column(Float, default=0.0)
    expected_hours = Column(Float, default=0.0)
    hours_difference = Column(Float, default=0.0)
    
    # Registros
    check_ins_count = Column(Integer, default=0)
    check_outs_count = Column(Integer, default=0)
    
    # Irregularidades
    late_check_ins = Column(Integer, default=0)
    early_check_outs = Column(Integer, default=0)
    missing_breaks = Column(Integer, default=0)
    absences = Column(Integer, default=0)
    
    # Estado
    is_locked = Column(Boolean, default=False)  # Reporte cerrado/validado
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    def __repr__(self):
        return f"<AttendanceReport {self.employee_id} {self.period_start}>"
