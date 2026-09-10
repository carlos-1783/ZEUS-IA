"""THALOS structured events — parsed from real logs and monitors."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base


class ThalosEvent(Base):
    __tablename__ = "thalos_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, default="info", index=True)
    message = Column(Text, nullable=False)
    source = Column(String(128), nullable=True, index=True)
    metadata_json = Column(Text, nullable=True)
    # AUDIT_THALOS_ESTRUCTURAL.md, paso 1: aislamiento multi-tenant real.
    # Nullable a propósito -- muchos eventos (parseo de logs de sistema,
    # patrones globales) no tienen un tenant claro al momento de escribirse.
    # Ver alembic/versions/0046_thalos_tables_company_id.py para el backfill
    # best-effort y 0047_thalos_row_level_security.py para el RLS real.
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
