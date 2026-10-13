"""Bandeja de entrada de ZEUS (recepcionista): documentos que llegan por foto/PDF.

Fase 2 / Jarvis: el usuario manda una foto (factura, ticket, nomina, albaran, contrato...)
como haria por WhatsApp. ZEUS la guarda en R2 (stored_files), la clasifica con el modelo de
vision y la asigna al agente responsable creando una revision pendiente (document_approvals).

Esta tabla es el registro de cada entrada: de que empresa es, que fichero, que dijo la IA
(tal cual, sin rellenar huecos), la validacion de coherencia y a quien se asigno. Nada de lo
que hay aqui contabiliza, registra facturas ni envia nada a terceros.
"""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.db.base import Base

# Estados de una entrada
STATUS_PENDING_CLASSIFICATION = "pendiente_clasificacion"  # guardada; IA no disponible o fallo
STATUS_CLASSIFIED = "clasificado"  # clasificada y asignada (revision humana pendiente)


class ZeusInboxItem(Base):
    __tablename__ = "zeus_inbox_items"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    stored_file_id = Column(
        String(32), ForeignKey("stored_files.id", ondelete="SET NULL"), nullable=True, index=True
    )
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(128), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False)
    note = Column(Text, nullable=True)  # texto opcional que acompana a la foto

    status = Column(String(32), nullable=False, default=STATUS_PENDING_CLASSIFICATION, index=True)
    doc_type = Column(String(32), nullable=True, index=True)
    confidence = Column(String(16), nullable=True)  # alta / media / baja
    extracted_json = Column(Text, nullable=True)  # campos extraidos (null si no legibles)
    validation_json = Column(Text, nullable=True)  # comprobaciones de coherencia
    classification_error = Column(Text, nullable=True)
    model = Column(String(64), nullable=True)

    assigned_agent = Column(String(32), nullable=True, index=True)
    document_approval_id = Column(
        Integer, ForeignKey("document_approvals.id", ondelete="SET NULL"), nullable=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    classified_at = Column(DateTime(timezone=True), nullable=True)
