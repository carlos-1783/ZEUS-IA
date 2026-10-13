"""Registro de envios salientes (email / WhatsApp) por empresa.

Fase 2 / envios con consentimiento: cada envio real (o bloqueo) hacia una persona queda aqui
con su empresa, el usuario que lo pidio, el canal, el motivo y el resultado. Sirve de log
verificable y de ventana para el limite de envios por empresa.

PII minimizada: el destinatario se guarda como hash SHA-256 (para contar por destinatario)
y como valor enmascarado (para que el dueno reconozca a quien se envio). Nunca el cuerpo.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.db.base import Base


class OutboundMessage(Base):
    __tablename__ = "outbound_messages"

    id = Column(Integer, primary_key=True, index=True)
    # NULL solo para envios de plataforma hechos por un superusuario.
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    channel = Column(String(20), nullable=False, index=True)  # email | whatsapp
    # direct | campaign | reservation_confirmation | platform
    purpose = Column(String(40), nullable=False, index=True)
    recipient_kind = Column(String(20), nullable=True)  # customer | employee | guest | platform
    recipient_ref_id = Column(Integer, nullable=True)
    recipient_hash = Column(String(64), nullable=False, index=True)
    recipient_masked = Column(String(120), nullable=True)
    status = Column(String(20), nullable=False, index=True)  # sent | failed | blocked
    detail = Column(String(300), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
