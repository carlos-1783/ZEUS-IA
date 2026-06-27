"""THALOS alerts — generated from events by threat engine."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base


class ThalosAlert(Base):
    __tablename__ = "thalos_alerts"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("thalos_events.id", ondelete="CASCADE"), nullable=True, index=True)
    level = Column(String(16), nullable=False, default="medium", index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    rule_id = Column(String(64), nullable=True, index=True)
    resolved = Column(Boolean, nullable=False, default=False, index=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
