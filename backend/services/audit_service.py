"""
ZEUS-IA - Audit Service
Logs inmutables de todas las acciones del sistema
CRÍTICO: Una vez creado, un log NUNCA se modifica o elimina
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from backend.models.audit_log import AuditLog, AuditAction


class AuditService:
    """
    Servicio de auditoría inmutable
    Registra todas las acciones críticas del sistema
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def _create_log(
        self,
        action: AuditAction,
        actor_type: str,
        actor_id: str,
        actor_name: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        target_name: Optional[str] = None,
        description: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        changes: Optional[Dict[str, Any]] = None,
        success: str = "success",
        error_message: Optional[str] = None,
        severity: str = "info",
        organization_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        contains_pii: str = "no",
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """
        Crea un log de auditoría (método interno)
        INMUTABLE: Una vez creado, nunca se modifica
        """
        
        log = AuditLog(
            action=action,
            action_description=description or action.value,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_name=actor_name,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            organization_id=organization_id,
            context=context,
            changes=changes,
            extra_metadata=extra_metadata,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            success=success,
            error_message=error_message,
            severity=severity,
            contains_pii=contains_pii
        )
        
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        
        return log
    
    # =============================================================================
    # DECISIONES
    # =============================================================================
    
    def log_decision_created(
        self,
        decision_id: str,
        agent_name: str,
        user_id: int,
        organization_id: str,
        confidence_score: float,
        context: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log de decisión creada"""
        return self._create_log(
            action=AuditAction.DECISION_CREATED,
            actor_type="agent",
            actor_id=agent_name,
            actor_name=agent_name,
            target_type="decision",
            target_id=decision_id,
            description=f"Agente {agent_name} creó decisión {decision_id}",
            context=context,
            organization_id=organization_id,
            severity="info",
            extra_metadata={"confidence_score": confidence_score, "user_id": user_id}
        )
    
    def log_decision_executed(
        self,
        decision_id: str,
        agent_name: str,
        result: Dict[str, Any],
        success: bool = True
    ) -> AuditLog:
        """Log de decisión ejecutada"""
        return self._create_log(
            action=AuditAction.DECISION_EXECUTED,
            actor_type="agent",
            actor_id=agent_name,
            actor_name=agent_name,
            target_type="decision",
            target_id=decision_id,
            description=f"Decisión {decision_id} ejecutada",
            changes=result,
            success="success" if success else "failure",
            severity="info" if success else "error"
        )
    
    def log_decision_rolled_back(
        self,
        decision_id: str,
        rolled_back_by: int,
        reason: str,
        rollback_data: Dict[str, Any]
    ) -> AuditLog:
        """Log de decisión revertida (rollback)"""
        return self._create_log(
            action=AuditAction.DECISION_ROLLED_BACK,
            actor_type="user",
            actor_id=str(rolled_back_by),
            actor_name=f"User {rolled_back_by}",
            target_type="decision",
            target_id=decision_id,
            description=f"Decisión {decision_id} revertida: {reason}",
            changes=rollback_data,
            severity="warning",
            extra_metadata={"reason": reason}
        )
    
    # =============================================================================
    # HITL (Human-In-The-Loop)
    # =============================================================================
    
    def log_hitl_requested(
        self,
        decision_id: str,
        agent_name: str,
        reason: str,
        priority: str
    ) -> AuditLog:
        """Log de solicitud HITL"""
        return self._create_log(
            action=AuditAction.HITL_REQUESTED,
            actor_type="agent",
            actor_id=agent_name,
            actor_name=agent_name,
            target_type="decision",
            target_id=decision_id,
            description=f"HITL solicitado para {decision_id}: {reason}",
            severity="warning" if priority in ["high", "critical"] else "info",
            extra_metadata={"reason": reason, "priority": priority}
        )
    
    def log_hitl_approved(
        self,
        decision_id: str,
        approved_by: int,
        notes: Optional[str] = None
    ) -> AuditLog:
        """Log de aprobación HITL"""
        return self._create_log(
            action=AuditAction.HITL_APPROVED,
            actor_type="user",
            actor_id=str(approved_by),
            actor_name=f"User {approved_by}",
            target_type="decision",
            target_id=decision_id,
            description=f"Decisión {decision_id} aprobada por usuario {approved_by}",
            severity="info",
            extra_metadata={"notes": notes}
        )
    
    def log_hitl_rejected(
        self,
        decision_id: str,
        rejected_by: int,
        notes: str
    ) -> AuditLog:
        """Log de rechazo HITL"""
        return self._create_log(
            action=AuditAction.HITL_REJECTED,
            actor_type="user",
            actor_id=str(rejected_by),
            actor_name=f"User {rejected_by}",
            target_type="decision",
            target_id=decision_id,
            description=f"Decisión {decision_id} rechazada por usuario {rejected_by}",
            severity="warning",
            extra_metadata={"notes": notes}
        )
    
    # =============================================================================
    # USUARIOS
    # =============================================================================
    
    def log_user_login(
        self,
        user_id: int,
        username: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log de login de usuario"""
        return self._create_log(
            action=AuditAction.USER_LOGIN,
            actor_type="user",
            actor_id=str(user_id),
            actor_name=username,
            description=f"Usuario {username} inició sesión",
            ip_address=ip_address,
            user_agent=user_agent,
            severity="info"
        )
    
    def log_user_logout(
        self,
        user_id: int,
        username: str
    ) -> AuditLog:
        """Log de logout de usuario"""
        return self._create_log(
            action=AuditAction.USER_LOGOUT,
            actor_type="user",
            actor_id=str(user_id),
            actor_name=username,
            description=f"Usuario {username} cerró sesión",
            severity="info"
        )
    
    # =============================================================================
    # AGENTES
    # =============================================================================
    
    def log_agent_error(
        self,
        agent_name: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log de error de agente"""
        return self._create_log(
            action=AuditAction.AGENT_ERROR,
            actor_type="agent",
            actor_id=agent_name,
            actor_name=agent_name,
            description=f"Error en agente {agent_name}",
            error_message=error_message,
            context=context,
            success="failure",
            severity="error"
        )
    
    # =============================================================================
    # SEGURIDAD
    # =============================================================================
    
    def log_security_threat(
        self,
        threat_type: str,
        description: str,
        ip_address: str,
        severity: str = "critical"
    ) -> AuditLog:
        """Log de amenaza de seguridad"""
        return self._create_log(
            action=AuditAction.SECURITY_THREAT_DETECTED,
            actor_type="system",
            actor_id="thalos",
            actor_name="THALOS Security Agent",
            description=description,
            ip_address=ip_address,
            severity=severity,
            extra_metadata={"threat_type": threat_type}
        )
    
    def log_ip_blocked(
        self,
        ip_address: str,
        reason: str
    ) -> AuditLog:
        """Log de IP bloqueada"""
        return self._create_log(
            action=AuditAction.IP_BLOCKED,
            actor_type="system",
            actor_id="thalos",
            actor_name="THALOS Security Agent",
            description=f"IP {ip_address} bloqueada: {reason}",
            ip_address=ip_address,
            severity="warning",
            extra_metadata={"reason": reason}
        )
    
    # =============================================================================
    # QUERIES
    # =============================================================================
    
    def get_logs(
        self,
        organization_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        actor_id: Optional[str] = None,
        target_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Obtiene logs de auditoría con filtros
        """
        query = self.db.query(AuditLog)
        
        if organization_id:
            query = query.filter(AuditLog.organization_id == organization_id)
        
        if action:
            query = query.filter(AuditLog.action == action)
        
        if actor_id:
            query = query.filter(AuditLog.actor_id == actor_id)
        
        if target_id:
            query = query.filter(AuditLog.target_id == target_id)
        
        if severity:
            query = query.filter(AuditLog.severity == severity)
        
        return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    def get_decision_history(self, decision_id: str) -> List[AuditLog]:
        """
        Obtiene historial completo de una decisión
        """
        return self.db.query(AuditLog).filter(
            AuditLog.target_type == "decision",
            AuditLog.target_id == decision_id
        ).order_by(AuditLog.timestamp.asc()).all()

