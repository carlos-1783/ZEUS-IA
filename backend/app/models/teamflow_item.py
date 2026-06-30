"""TeamFlow items — cross-agent flows persisted in DB."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base

VALID_STATUSES = frozenset({"draft", "pending", "approved", "rejected", "in_progress", "completed"})


class TeamFlowItem(Base):
    __tablename__ = "teamflow_items"

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_agent = Column(String(64), nullable=False, index=True)
    source_agent = Column(String(64), nullable=True, index=True)
    target_agent = Column(String(64), nullable=True, index=True)
    workflow_id = Column(String(128), nullable=True, index=True)
    item_type = Column(String(64), nullable=False, default="flow", index=True)
    title = Column(String(255), nullable=False)
    content_json = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="draft", index=True)
    execution_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
