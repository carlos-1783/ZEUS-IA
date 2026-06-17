"""Auditoría de decisiones zeus_total_system_closure_v1."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.db.base import Base


class ZeusClosureAudit(Base):
    __tablename__ = "zeus_closure_audits"

    id = Column(Integer, primary_key=True, index=True)
    layer = Column(String(32), nullable=False, index=True)  # api|service|agent|event_bus|db
    domain = Column(String(32), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    actor_id = Column(String(64), nullable=True)
    actor_email = Column(String(255), nullable=True)
    target_id = Column(String(64), nullable=True)
    company_id = Column(Integer, nullable=True, index=True)
    result = Column(String(32), nullable=False)  # allowed|rejected|observed
    execution_mode = Column(String(16), nullable=False, default="real")
    human_message = Column(String(500), nullable=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
