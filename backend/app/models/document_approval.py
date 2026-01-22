"""
🛡️ Document Approval Model
Modelo para persistir documentos legales y fiscales pendientes de aprobación
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import json


class DocumentApproval(Base):
    """
    Documento generado por RAFAEL o JUSTICIA pendiente de aprobación del cliente.
    """
    __tablename__ = "document_approvals"

    id = Column(Integer, primary_key=True, index=True)
    
    # Usuario que solicitó el documento
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Agente que generó el documento
    agent_name = Column(String(50), nullable=False, index=True)  # "RAFAEL" o "JUSTICIA"
    
    # Tipo de documento
    document_type = Column(String(100), nullable=False)  # "invoice", "tax", "contract", "gdpr", etc.
    
    # Contenido del documento (JSON)
    document_payload_json = Column(Text, nullable=False)  # JSON serializado
    
    # Estado del documento
    status = Column(String(50), nullable=False, default="draft", index=True)  
    # Estados: draft, pending_approval, pending_review, approved, approved_by_manager, 
    #          rejected, sent_to_advisor, exported, filed_external, failed
    
    # Email del asesor al que se enviará
    advisor_email = Column(String(255), nullable=True)
    
    # Campos fiscales específicos (para documentos de TPV)
    ticket_id = Column(String(100), nullable=True, index=True)  # ID del ticket TPV que generó este documento
    fiscal_document_type = Column(String(50), nullable=True)  # ticket, factura, modelo_303, resumen_diario, etc.
    export_format = Column(String(20), nullable=True)  # json, xml, pdf
    exported_at = Column(DateTime(timezone=True), nullable=True)  # Timestamp de exportación
    filed_external_at = Column(DateTime(timezone=True), nullable=True)  # Timestamp de presentación externa (Hacienda)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Log de auditoría (JSON)
    audit_log_json = Column(Text, nullable=True)  # JSON con historial de acciones
    
    # Relationship
    user = relationship("User", back_populates="document_approvals")
    
    def __repr__(self):
        return f"<DocumentApproval id={self.id} agent={self.agent_name} type={self.document_type} status={self.status}>"
    
    def to_dict(self):
        """Convertir a diccionario"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "agent_name": self.agent_name,
            "document_type": self.document_type,
            "document_payload": json.loads(self.document_payload_json) if self.document_payload_json else {},
            "status": self.status,
            "advisor_email": self.advisor_email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "ticket_id": self.ticket_id,
            "fiscal_document_type": self.fiscal_document_type,
            "export_format": self.export_format,
            "exported_at": self.exported_at.isoformat() if self.exported_at else None,
            "filed_external_at": self.filed_external_at.isoformat() if self.filed_external_at else None,
            "audit_log": json.loads(self.audit_log_json) if self.audit_log_json else []
        }
    
    @property
    def document_payload(self):
        """Obtener payload como dict"""
        if self.document_payload_json:
            return json.loads(self.document_payload_json)
        return {}
    
    @document_payload.setter
    def document_payload(self, value):
        """Establecer payload desde dict"""
        self.document_payload_json = json.dumps(value, ensure_ascii=False) if value else "{}"
    
    @property
    def audit_log(self):
        """Obtener log de auditoría como list"""
        if self.audit_log_json:
            return json.loads(self.audit_log_json)
        return []
    
    @audit_log.setter
    def audit_log(self, value):
        """Establecer log de auditoría desde list"""
        self.audit_log_json = json.dumps(value, ensure_ascii=False) if value else "[]"

