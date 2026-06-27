"""PERSEO V2 async job queue — persisted for workers and observability."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class PerseoJob(Base):
    __tablename__ = "perseo_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), unique=True, nullable=False, index=True)
    job_type = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    progress = Column(Integer, nullable=False, default=0)
    user_id = Column(Integer, nullable=False, index=True)
    transaction_id = Column(String(36), nullable=True, index=True)
    input_json = Column(Text, nullable=True)
    output_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
