"""
ZEUS-IA - Decision Model
Modelo de decisiones tomadas por agentes IA
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Float, Text, Enum
from sqlalchemy.sql import func
import enum
from backend.models.database import Base


class DecisionStatus(str, enum.Enum):
    """Estados de una decisión"""
    PENDING = "pending"           # Esperando ejecución
    APPROVED = "approved"         # Aprobada por humano (HITL)
    REJECTED = "rejected"         # Rechazada por humano (HITL)
    EXECUTED = "executed"         # Ejecutada exitosamente
    FAILED = "failed"             # Falló la ejecución
    ROLLED_BACK = "rolled_back"   # Deshecha (rollback)
    SHADOW = "shadow"             # Modo shadow (no ejecutada, solo log)


class Decision(Base):
    """
    Decisión tomada por un agente IA
    Incluye metadata completa para explainability y auditoría
    """
    
    __tablename__ = "decisions"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(String(100), unique=True, index=True)  # UUID generado
    
    # Agente que tomó la decisión
    agent_name = Column(String(50), index=True)  # PERSEO, RAFAEL, THALOS, etc.
    agent_role = Column(String(100))
    
    # Usuario/Organización
    user_id = Column(Integer, index=True)
    organization_id = Column(String(100), index=True)
    
    # Contexto de la decisión
    request_context = Column(JSON)  # Input original del usuario
    prompt_used = Column(Text)      # Prompt enviado a OpenAI
    
    # Respuesta y reasoning
    response = Column(Text)                 # Respuesta del agente
    reasoning = Column(Text)                # Explicación del razonamiento
    alternatives_considered = Column(JSON)  # Alternativas que consideró
    
    # Métricas de confianza
    confidence_score = Column(Float)        # 0.0 - 1.0
    risk_score = Column(Float)              # 0.0 - 1.0
    impact_score = Column(Float)            # 0.0 - 1.0
    
    # HITL (Human-In-The-Loop)
    hitl_required = Column(Boolean, default=False)
    hitl_reason = Column(String(255))
    hitl_approved_by = Column(Integer)      # User ID que aprobó
    hitl_approved_at = Column(DateTime(timezone=True))
    hitl_notes = Column(Text)
    
    # Estado y ejecución
    status = Column(Enum(DecisionStatus), default=DecisionStatus.PENDING)
    executed_at = Column(DateTime(timezone=True))
    execution_result = Column(JSON)  # Resultado de la ejecución
    execution_error = Column(Text)   # Error si falló
    
    # Rollback
    can_rollback = Column(Boolean, default=False)
    rollback_data = Column(JSON)     # Datos para deshacer
    rolled_back_at = Column(DateTime(timezone=True))
    rolled_back_by = Column(Integer)  # User ID que hizo rollback
    
    # Shadow mode
    is_shadow_mode = Column(Boolean, default=False)
    
    # Costos
    openai_cost = Column(Float, default=0.0)
    tokens_used = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Tags y categorización
    tags = Column(JSON, default=list)
    category = Column(String(50))  # marketing, fiscal, security, legal
    
    def __repr__(self):
        return f"<Decision {self.decision_id} by {self.agent_name} ({self.status})>"
    
    def to_dict(self):
        """Convierte a diccionario"""
        return {
            "id": self.id,
            "decision_id": self.decision_id,
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "request_context": self.request_context,
            "response": self.response,
            "reasoning": self.reasoning,
            "confidence_score": self.confidence_score,
            "risk_score": self.risk_score,
            "hitl_required": self.hitl_required,
            "status": self.status.value if self.status else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "can_rollback": self.can_rollback,
            "is_shadow_mode": self.is_shadow_mode,
            "openai_cost": self.openai_cost,
            "tokens_used": self.tokens_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "tags": self.tags,
            "category": self.category,
        }

