"""Cross-module domain events — DB-backed event bus."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base


class ZeusDomainEvent(Base):
    __tablename__ = "zeus_domain_events"

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    event_name = Column(String(64), nullable=False, index=True)
    source_module = Column(String(32), nullable=False, index=True)
    payload_json = Column(Text, nullable=True)
    propagated_to = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
