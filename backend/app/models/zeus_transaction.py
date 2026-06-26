"""ZEUS transactional orchestration records."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class ZeusTransaction(Base):
    __tablename__ = "zeus_transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(36), unique=True, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    execution_mode_at_start = Column(String(32), nullable=True)
    initiator_json = Column(Text, nullable=True)
    context_json = Column(Text, nullable=True)
    modules_involved_json = Column(Text, nullable=True)
    steps_json = Column(Text, nullable=True)
    locks_json = Column(Text, nullable=True)
    validation_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    errors_json = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=True)
    idempotency_key = Column(String(128), nullable=True, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
