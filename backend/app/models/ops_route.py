"""AFRODITA OPS routes — persistencia de rutas operativas."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class OpsRoute(Base):
    __tablename__ = "ops_routes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    origin = Column(String(255), nullable=False)
    destination = Column(String(255), nullable=False)
    distance = Column(Float, nullable=False, default=0.0)
    route_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
