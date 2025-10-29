"""
ZEUS-IA - HITL Service
Human-In-The-Loop: Sistema de aprobación humana automático
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from backend.models.hitl_queue import HITLQueue, HITLStatus
from backend.models.decision import Decision, DecisionStatus
from backend.models.user import User
from backend.services.audit_service import AuditService


class HITLService:
    """
    Servicio de Human-In-The-Loop
    Gestiona decisiones que requieren aprobación humana
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
    
    def create_hitl_request(
        self,
        decision: Decision,
        reason: str,
        triggers: List[str],
        priority: str = "medium",
        sla_minutes: int = 15
    ) -> HITLQueue:
        """
        Crea una solicitud HITL para una decisión
        
        Args:
            decision: Decisión que requiere aprobación
            reason: Razón por la que requiere aprobación humana
            triggers: Lista de reglas que se dispararon
            priority: low, medium, high, critical
            sla_minutes: Minutos para el deadline SLA
        """
        
        # Crear entry en cola HITL
        hitl_entry = HITLQueue(
            decision_id=decision.decision_id,
            agent_name=decision.agent_name,
            agent_role=decision.agent_role,
            user_id=decision.user_id,
            organization_id=decision.organization_id,
            request_summary=self._generate_summary(decision),
            full_context=decision.request_context,
            agent_recommendation=decision.response,
            confidence_score=decision.confidence_score,
            risk_score=decision.risk_score,
            hitl_reason=reason,
            hitl_triggers=triggers,
            status=HITLStatus.PENDING,
            priority=priority,
            sla_deadline=datetime.utcnow() + timedelta(minutes=sla_minutes),
            extra_metadata={
                "created_by": "hitl_service",
                "decision_category": decision.category,
                "openai_cost": decision.openai_cost
            }
        )
        
        self.db.add(hitl_entry)
        self.db.commit()
        self.db.refresh(hitl_entry)
        
        # Audit log
        self.audit.log_hitl_requested(
            decision_id=decision.decision_id,
            agent_name=decision.agent_name,
            reason=reason,
            priority=priority
        )
        
        # Auto-asignar si hay usuario preferido
        self._auto_assign(hitl_entry)
        
        # Notificar
        self.notify_human(hitl_entry.id)
        
        return hitl_entry
    
    def notify_human(self, hitl_id: int) -> bool:
        """
        Notifica a un humano sobre una solicitud HITL
        """
        hitl_entry = self.db.query(HITLQueue).filter(HITLQueue.id == hitl_id).first()
        if not hitl_entry:
            return False
        
        # TODO: Implementar notificaciones reales (email, SMS, Slack)
        # Por ahora solo marcamos como notificado
        
        hitl_entry.notification_sent = True
        hitl_entry.notified_at = datetime.utcnow()
        hitl_entry.notification_attempts += 1
        hitl_entry.last_notification_at = datetime.utcnow()
        hitl_entry.status = HITLStatus.NOTIFIED
        hitl_entry.notification_method = ["email"]  # TODO: Implementar métodos reales
        
        self.db.commit()
        
        return True
    
    def approve(
        self,
        hitl_id: int,
        user_id: int,
        notes: Optional[str] = None,
        modifications: Optional[Dict[str, Any]] = None
    ) -> Decision:
        """
        Aprueba una decisión HITL
        """
        hitl_entry = self.db.query(HITLQueue).filter(HITLQueue.id == hitl_id).first()
        if not hitl_entry:
            raise ValueError(f"HITL entry {hitl_id} not found")
        
        decision = self.db.query(Decision).filter(
            Decision.decision_id == hitl_entry.decision_id
        ).first()
        
        if not decision:
            raise ValueError(f"Decision {hitl_entry.decision_id} not found")
        
        # Actualizar HITL entry
        hitl_entry.status = HITLStatus.APPROVED
        hitl_entry.reviewed_by = user_id
        hitl_entry.reviewed_at = datetime.utcnow()
        hitl_entry.resolved_at = datetime.utcnow()
        hitl_entry.human_decision = "approve"
        hitl_entry.human_notes = notes
        hitl_entry.human_modifications = modifications
        
        # Actualizar decisión
        decision.status = DecisionStatus.APPROVED
        decision.hitl_approved_by = user_id
        decision.hitl_approved_at = datetime.utcnow()
        decision.hitl_notes = notes
        
        self.db.commit()
        
        # Audit log
        self.audit.log_hitl_approved(
            decision_id=decision.decision_id,
            approved_by=user_id,
            notes=notes
        )
        
        return decision
    
    def reject(
        self,
        hitl_id: int,
        user_id: int,
        notes: str
    ) -> Decision:
        """
        Rechaza una decisión HITL
        """
        hitl_entry = self.db.query(HITLQueue).filter(HITLQueue.id == hitl_id).first()
        if not hitl_entry:
            raise ValueError(f"HITL entry {hitl_id} not found")
        
        decision = self.db.query(Decision).filter(
            Decision.decision_id == hitl_entry.decision_id
        ).first()
        
        if not decision:
            raise ValueError(f"Decision {hitl_entry.decision_id} not found")
        
        # Actualizar HITL entry
        hitl_entry.status = HITLStatus.REJECTED
        hitl_entry.reviewed_by = user_id
        hitl_entry.reviewed_at = datetime.utcnow()
        hitl_entry.resolved_at = datetime.utcnow()
        hitl_entry.human_decision = "reject"
        hitl_entry.human_notes = notes
        
        # Actualizar decisión
        decision.status = DecisionStatus.REJECTED
        decision.hitl_approved_by = user_id
        decision.hitl_approved_at = datetime.utcnow()
        decision.hitl_notes = notes
        
        self.db.commit()
        
        # Audit log
        self.audit.log_hitl_rejected(
            decision_id=decision.decision_id,
            rejected_by=user_id,
            notes=notes
        )
        
        return decision
    
    def escalate(
        self,
        hitl_id: int,
        escalate_to_user_id: int,
        reason: str
    ) -> HITLQueue:
        """
        Escala una solicitud HITL a un superior
        """
        hitl_entry = self.db.query(HITLQueue).filter(HITLQueue.id == hitl_id).first()
        if not hitl_entry:
            raise ValueError(f"HITL entry {hitl_id} not found")
        
        hitl_entry.escalated = True
        hitl_entry.escalated_to = escalate_to_user_id
        hitl_entry.escalated_at = datetime.utcnow()
        hitl_entry.escalation_reason = reason
        hitl_entry.status = HITLStatus.ESCALATED
        hitl_entry.priority = "high"  # Aumentar prioridad
        
        self.db.commit()
        
        # Notificar al superior
        self.notify_human(hitl_id)
        
        return hitl_entry
    
    def get_pending(
        self,
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
        priority: Optional[str] = None
    ) -> List[HITLQueue]:
        """
        Obtiene solicitudes HITL pendientes
        """
        query = self.db.query(HITLQueue).filter(
            HITLQueue.status.in_([HITLStatus.PENDING, HITLStatus.NOTIFIED, HITLStatus.IN_REVIEW])
        )
        
        if organization_id:
            query = query.filter(HITLQueue.organization_id == organization_id)
        
        if user_id:
            query = query.filter(HITLQueue.assigned_to == user_id)
        
        if priority:
            query = query.filter(HITLQueue.priority == priority)
        
        return query.order_by(HITLQueue.created_at.desc()).all()
    
    def check_overdue(self) -> List[HITLQueue]:
        """
        Verifica y marca solicitudes HITL vencidas
        Retorna lista de vencidas para escalar
        """
        now = datetime.utcnow()
        
        overdue = self.db.query(HITLQueue).filter(
            HITLQueue.status.in_([HITLStatus.PENDING, HITLQueue.NOTIFIED]),
            HITLQueue.sla_deadline < now,
            HITLQueue.is_overdue == False
        ).all()
        
        for entry in overdue:
            entry.is_overdue = True
            entry.status = HITLStatus.EXPIRED
        
        self.db.commit()
        
        return overdue
    
    def _generate_summary(self, decision: Decision) -> str:
        """Genera resumen para humano"""
        return f"""
Agente: {decision.agent_name}
Categoría: {decision.category}
Confianza: {decision.confidence_score:.0%}
Riesgo: {decision.risk_score:.0%}

Recomendación:
{decision.response[:200]}...
        """.strip()
    
    def _auto_assign(self, hitl_entry: HITLQueue):
        """Auto-asigna HITL a usuario apropiado"""
        # TODO: Implementar lógica de asignación inteligente
        # Por ahora, buscar admin de la organización
        
        admin = self.db.query(User).filter(
            User.organization_id == hitl_entry.organization_id,
            User.role.in_(["admin", "manager"]),
            User.hitl_enabled == True,
            User.is_active == True
        ).first()
        
        if admin:
            hitl_entry.assigned_to = admin.id
            hitl_entry.assigned_at = datetime.utcnow()
            self.db.commit()

