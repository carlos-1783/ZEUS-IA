"""Preferencias de aplicación por usuario (idioma, tema, 2FA flag, timeout inactividad)."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    language = Column(String(16), nullable=False, default="es")
    theme = Column(String(32), nullable=False, default="dark")
    two_factor_enabled = Column(Boolean, nullable=False, default=False)
    session_timeout = Column(Integer, nullable=False, default=60)  # minutos
    api_key_hash = Column(String(64), nullable=True)
    api_key_prefix = Column(String(16), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    user = relationship("User", backref="user_settings_row", uselist=False)

    def __repr__(self) -> str:
        return f"<UserSettings user_id={self.user_id}>"
