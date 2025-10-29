"""
ZEUS-IA - Audit Log Model
Logs inmutables de todas las acciones del sistema
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Enum
from sqlalchemy.sql import func
import enum
from backend.models.database import Base


class AuditAction(str, enum.Enum):
    """Tipos de acciones auditables"""
    # Decisiones
    DECISION_CREATED = "decision_created"
    DECISION_EXECUTED = "decision_executed"
    DECISION_APPROVED = "decision_approved"
    DECISION_REJECTED = "decision_rejected"
    DECISION_ROLLED_BACK = "decision_rolled_back"
    
    # Usuarios
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    
    # Agentes
    AGENT_ACTIVATED = "agent_activated"
    AGENT_DEACTIVATED = "agent_deactivated"
    AGENT_ERROR = "agent_error"
    
    # Sistema
    SYSTEM_STARTED = "system_started"
    SYSTEM_ERROR = "system_error"
    CONFIG_CHANGED = "config_changed"
    
    # Seguridad
    SECURITY_THREAT_DETECTED = "security_threat_detected"
    IP_BLOCKED = "ip_blocked"
    CREDENTIALS_REVOKED = "credentials_revoked"
    
    # HITL
    HITL_REQUESTED = "hitl_requested"
    HITL_APPROVED = "hitl_approved"
    HITL_REJECTED = "hitl_rejected"


class AuditLog(Base):
    """
    Log inmutable de auditoría
    CRÍTICO: Una vez creado, NUNCA se modifica o elimina
    """
    
    __tablename__ = "audit_logs"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Timestamp (INMUTABLE)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Acción
    action = Column(Enum(AuditAction), nullable=False, index=True)
    action_description = Column(String(500))
    
    # Actor (quién realizó la acción)
    actor_type = Column(String(50))  # user, agent, system
    actor_id = Column(String(100), index=True)  # user_id, agent_name, "system"
    actor_name = Column(String(255))
    
    # Target (sobre qué/quién se realizó)
    target_type = Column(String(50))  # decision, user, agent, system
    target_id = Column(String(100), index=True)
    target_name = Column(String(255))
    
    # Organización
    organization_id = Column(String(100), index=True)
    
    # Contexto completo
    context = Column(JSON)  # Estado antes de la acción
    changes = Column(JSON)  # Cambios realizados
    extra_metadata = Column(JSON)  # Metadata adicional
    
    # Request info
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    request_id = Column(String(100), index=True)  # Para trace distribuido
    
    # Resultado
    success = Column(String(20))  # success, failure, partial
    error_message = Column(Text)
    
    # Severity
    severity = Column(String(20))  # info, warning, error, critical
    
    # GDPR y compliance
    contains_pii = Column(String(10), default="no")  # yes, no, masked
    retention_policy = Column(String(50))  # standard, extended, legal_hold
    
    def __repr__(self):
        return f"<AuditLog {self.id}: {self.action} by {self.actor_name} at {self.timestamp}>"
    
    def to_dict(self):
        """Convierte a diccionario"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "action": self.action.value if self.action else None,
            "action_description": self.action_description,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "organization_id": self.organization_id,
            "context": self.context,
            "changes": self.changes,
            "extra_metadata": self.extra_metadata,
            "ip_address": self.ip_address,
            "success": self.success,
            "error_message": self.error_message,
            "severity": self.severity,
            "contains_pii": self.contains_pii,
        }

