"""
ZEUS-IA - HITL Queue Model
Cola de decisiones que requieren aprobación humana
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Float, Text, Enum
from sqlalchemy.sql import func
import enum
from backend.models.database import Base


class HITLStatus(str, enum.Enum):
    """Estados de HITL"""
    PENDING = "pending"         # Esperando revisión humana
    NOTIFIED = "notified"       # Humano notificado
    IN_REVIEW = "in_review"     # Humano revisando
    APPROVED = "approved"       # Aprobado
    REJECTED = "rejected"       # Rechazado
    EXPIRED = "expired"         # Tiempo límite excedido
    ESCALATED = "escalated"     # Escalado a superior


class HITLQueue(Base):
    """
    Cola de Human-In-The-Loop
    Decisiones que esperan aprobación humana
    """
    
    __tablename__ = "hitl_queue"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # Relación con decisión
    decision_id = Column(String(100), unique=True, index=True, nullable=False)
    
    # Agente que solicita aprobación
    agent_name = Column(String(50), index=True)
    agent_role = Column(String(100))
    
    # Usuario/Organización
    user_id = Column(Integer, index=True)
    organization_id = Column(String(100), index=True)
    
    # Contexto de la solicitud
    request_summary = Column(Text)  # Resumen para el humano
    full_context = Column(JSON)     # Contexto completo
    
    # Recomendación del agente
    agent_recommendation = Column(Text)
    confidence_score = Column(Float)
    risk_score = Column(Float)
    
    # Razón por la que requiere HITL
    hitl_reason = Column(String(500))
    hitl_triggers = Column(JSON)  # Qué reglas se dispararon
    
    # Estado
    status = Column(Enum(HITLStatus), default=HITLStatus.PENDING, index=True)
    priority = Column(String(20), default="medium")  # low, medium, high, critical
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    notified_at = Column(DateTime(timezone=True))
    reviewed_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    
    # SLA
    sla_deadline = Column(DateTime(timezone=True))  # Deadline para respuesta
    is_overdue = Column(Boolean, default=False)
    
    # Asignación
    assigned_to = Column(Integer)  # User ID asignado
    assigned_at = Column(DateTime(timezone=True))
    assigned_by = Column(Integer)
    
    # Revisión humana
    reviewed_by = Column(Integer)  # User ID que revisó
    human_decision = Column(String(20))  # approve, reject, modify
    human_notes = Column(Text)
    human_modifications = Column(JSON)  # Si modificó la decisión
    
    # Notificaciones
    notification_sent = Column(Boolean, default=False)
    notification_method = Column(JSON)  # email, sms, slack, etc.
    notification_attempts = Column(Integer, default=0)
    last_notification_at = Column(DateTime(timezone=True))
    
    # Escalación
    escalated = Column(Boolean, default=False)
    escalated_to = Column(Integer)  # User ID superior
    escalated_at = Column(DateTime(timezone=True))
    escalation_reason = Column(String(500))
    
    # Metadata
    extra_metadata = Column(JSON)
    tags = Column(JSON, default=list)
    
    def __repr__(self):
        return f"<HITLQueue {self.decision_id}: {self.status} (Priority: {self.priority})>"
    
    def to_dict(self):
        """Convierte a diccionario"""
        return {
            "id": self.id,
            "decision_id": self.decision_id,
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "request_summary": self.request_summary,
            "agent_recommendation": self.agent_recommendation,
            "confidence_score": self.confidence_score,
            "risk_score": self.risk_score,
            "hitl_reason": self.hitl_reason,
            "status": self.status.value if self.status else None,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "sla_deadline": self.sla_deadline.isoformat() if self.sla_deadline else None,
            "is_overdue": self.is_overdue,
            "assigned_to": self.assigned_to,
            "reviewed_by": self.reviewed_by,
            "human_decision": self.human_decision,
            "human_notes": self.human_notes,
            "notification_sent": self.notification_sent,
            "escalated": self.escalated,
            "tags": self.tags,
        }

