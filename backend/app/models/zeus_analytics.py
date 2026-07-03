"""ZEUS executive analytics — events, alerts, automations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base


class ZeusEvent(Base):
    __tablename__ = "zeus_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    type = Column(String(64), nullable=False, index=True)
    agent = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="success", index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )


class ZeusAlert(Base):
    __tablename__ = "zeus_alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    level = Column(String(16), nullable=False, default="medium", index=True)
    message = Column(Text, nullable=False)
    resolved = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )


class ZeusAutomation(Base):
    __tablename__ = "zeus_automations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(String(32), nullable=False, default="active", index=True)
    last_run = Column(DateTime(timezone=True), nullable=True)
