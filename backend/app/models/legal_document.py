"""Legal documents — persisted contracts and signed artifacts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base


class LegalDocument(Base):
    __tablename__ = "legal_documents"

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    doc_type = Column(String(64), nullable=False, index=True)
    content = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="draft", index=True)
    owner_agent = Column(String(64), nullable=False, default="JUSTICIA", index=True)
    version = Column(Integer, nullable=False, default=1)
    parent_id = Column(Integer, ForeignKey("legal_documents.id", ondelete="SET NULL"), nullable=True)
    signature_hash = Column(String(128), nullable=True)
    signer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
