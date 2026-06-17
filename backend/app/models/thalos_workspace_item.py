"""THALOS workspace items — persistencia para UI."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base


class ThalosWorkspaceItem(Base):
    __tablename__ = "thalos_workspace_items"

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    item_type = Column(String(16), nullable=False, index=True)  # audit | alert | backup
    workspace_document_id = Column(Integer, ForeignKey("document_approvals.id", ondelete="SET NULL"), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(16), nullable=False, default="completed")  # completed | warning | critical
    data_size_kb = Column(Integer, nullable=False, default=0)
    title = Column(String(255), nullable=True)
    source = Column(String(64), nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
