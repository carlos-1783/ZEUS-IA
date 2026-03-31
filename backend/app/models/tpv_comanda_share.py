"""Instantánea de comanda TPV para compartir con empleados (otro dispositivo)."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.db.base import Base


class TPVComandaShare(Base):
    __tablename__ = "tpv_comanda_shares"

    id = Column(String(36), primary_key=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<TPVComandaShare {self.id} owner={self.owner_user_id}>"
