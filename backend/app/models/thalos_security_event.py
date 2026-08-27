"""THALOS security events — auditoría de anomalías y acciones (thalos_safe_audit_v1)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base


class ThalosSecurityEvent(Base):
    __tablename__ = "thalos_security_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, default="info", index=True)
    source = Column(String(64), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_email = Column(String(255), nullable=True, index=True)
    ip_address = Column(String(64), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    details_json = Column(Text, nullable=True)
    action_taken = Column(String(128), nullable=True)
    decision_rule = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ThalosLoginAttempt(Base):
    __tablename__ = "thalos_login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(64), nullable=True, index=True)
    success = Column(Integer, nullable=False, default=0)  # 0 fail, 1 ok
    # AUDIT_THALOS_ESTRUCTURAL.md, paso 1: aislamiento multi-tenant real.
    # Nullable e irreductiblemente incompleto por diseño: los intentos de
    # login con un email que no corresponde a ningún usuario real (el caso
    # de uso central de esta tabla -- detectar fuerza bruta con emails
    # inventados) nunca podrán atribuirse a una empresa. Ver
    # 0046_thalos_tables_company_id.py (backfill best-effort) y
    # 0047_thalos_row_level_security.py (RLS real).
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
