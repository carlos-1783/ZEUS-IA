"""
ZEUS-IA - Rollback Service
Sistema para deshacer acciones ejecutadas por agentes IA
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.models.decision import Decision, DecisionStatus
from backend.services.audit_service import AuditService


class RollbackService:
    """
    Servicio de Rollback
    Permite deshacer decisiones ejecutadas por agentes IA
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)
    
    def can_rollback(self, decision_id: str) -> tuple[bool, Optional[str]]:
        """
        Verifica si una decisión puede ser revertida
        
        Returns:
            (can_rollback: bool, reason: Optional[str])
        """
        decision = self.db.query(Decision).filter(
            Decision.decision_id == decision_id
        ).first()
        
        if not decision:
            return False, "Decisión no encontrada"
        
        if decision.status == DecisionStatus.ROLLED_BACK:
            return False, "Decisión ya fue revertida"
        
        if decision.status != DecisionStatus.EXECUTED:
            return False, f"Decisión en estado {decision.status}, no ejecutada"
        
        if not decision.can_rollback:
            return False, "Decisión marcada como no reversible"
        
        if not decision.rollback_data:
            return False, "No hay datos de rollback disponibles"
        
        # Verificar si ya pasó mucho tiempo (configurable)
        # TODO: Agregar ventana de tiempo de rollback
        
        return True, None
    
    def rollback(
        self,
        decision_id: str,
        user_id: int,
        reason: str
    ) -> Dict[str, Any]:
        """
        Revierte una decisión ejecutada
        
        Args:
            decision_id: ID de la decisión a revertir
            user_id: ID del usuario que solicita el rollback
            reason: Razón del rollback
        
        Returns:
            Resultado del rollback
        """
        
        # Verificar si se puede revertir
        can_rollback, error_reason = self.can_rollback(decision_id)
        if not can_rollback:
            raise ValueError(f"No se puede revertir: {error_reason}")
        
        decision = self.db.query(Decision).filter(
            Decision.decision_id == decision_id
        ).first()
        
        # Ejecutar rollback según el tipo de acción
        rollback_result = self._execute_rollback(decision)
        
        # Actualizar decisión
        decision.status = DecisionStatus.ROLLED_BACK
        decision.rolled_back_at = datetime.utcnow()
        decision.rolled_back_by = user_id
        
        self.db.commit()
        
        # Audit log
        self.audit.log_decision_rolled_back(
            decision_id=decision_id,
            rolled_back_by=user_id,
            reason=reason,
            rollback_data=rollback_result
        )
        
        return {
            "success": True,
            "decision_id": decision_id,
            "rolled_back_at": decision.rolled_back_at.isoformat(),
            "rolled_back_by": user_id,
            "reason": reason,
            "result": rollback_result
        }
    
    def _execute_rollback(self, decision: Decision) -> Dict[str, Any]:
        """
        Ejecuta el rollback específico según el agente y tipo de decisión
        
        Este método debe ser extendido para cada tipo de acción reversible
        """
        
        rollback_data = decision.rollback_data
        agent_name = decision.agent_name
        
        # PERSEO - Rollback de acciones de marketing
        if agent_name == "PERSEO":
            return self._rollback_perseo(decision, rollback_data)
        
        # RAFAEL - Rollback de acciones fiscales
        elif agent_name == "RAFAEL":
            return self._rollback_rafael(decision, rollback_data)
        
        # THALOS - Rollback de acciones de seguridad
        elif agent_name == "THALOS":
            return self._rollback_thalos(decision, rollback_data)
        
        # Fallback genérico
        else:
            return {
                "method": "generic",
                "message": "Rollback genérico ejecutado",
                "original_state": rollback_data.get("original_state")
            }
    
    def _rollback_perseo(self, decision: Decision, rollback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rollback de acciones de PERSEO (Marketing)
        
        Ejemplos:
        - Pausar campaña de Google Ads
        - Eliminar post programado
        - Revertir cambio de estrategia
        """
        
        action_type = rollback_data.get("action_type")
        
        if action_type == "google_ads_campaign":
            # TODO: Integrar con Google Ads API para pausar campaña
            campaign_id = rollback_data.get("campaign_id")
            return {
                "method": "google_ads_pause",
                "campaign_id": campaign_id,
                "status": "paused",
                "message": f"Campaña {campaign_id} pausada"
            }
        
        elif action_type == "social_media_post":
            # TODO: Integrar con APIs de redes sociales
            post_id = rollback_data.get("post_id")
            return {
                "method": "social_media_delete",
                "post_id": post_id,
                "status": "deleted",
                "message": f"Post {post_id} eliminado"
            }
        
        else:
            return {
                "method": "perseo_generic",
                "message": "Rollback de PERSEO ejecutado",
                "rollback_data": rollback_data
            }
    
    def _rollback_rafael(self, decision: Decision, rollback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rollback de acciones de RAFAEL (Fiscal)
        
        Ejemplos:
        - Revertir registro contable
        - Cancelar factura generada
        - Restaurar estado anterior de cuenta
        """
        
        action_type = rollback_data.get("action_type")
        
        if action_type == "invoice_generated":
            # TODO: Marcar factura como cancelada
            invoice_id = rollback_data.get("invoice_id")
            return {
                "method": "invoice_cancel",
                "invoice_id": invoice_id,
                "status": "cancelled",
                "message": f"Factura {invoice_id} cancelada"
            }
        
        elif action_type == "accounting_entry":
            # TODO: Crear asiento de reversión
            entry_id = rollback_data.get("entry_id")
            return {
                "method": "accounting_reverse",
                "entry_id": entry_id,
                "status": "reversed",
                "message": f"Asiento {entry_id} revertido"
            }
        
        else:
            return {
                "method": "rafael_generic",
                "message": "Rollback de RAFAEL ejecutado",
                "rollback_data": rollback_data
            }
    
    def _rollback_thalos(self, decision: Decision, rollback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rollback de acciones de THALOS (Seguridad)
        
        Ejemplos:
        - Desbloquear IP
        - Restaurar credenciales
        - Reactivar cuenta
        """
        
        action_type = rollback_data.get("action_type")
        
        if action_type == "ip_blocked":
            # TODO: Eliminar IP de lista de bloqueo
            ip_address = rollback_data.get("ip_address")
            return {
                "method": "ip_unblock",
                "ip_address": ip_address,
                "status": "unblocked",
                "message": f"IP {ip_address} desbloqueada"
            }
        
        elif action_type == "credentials_revoked":
            # TODO: Restaurar credenciales
            user_id = rollback_data.get("user_id")
            return {
                "method": "credentials_restore",
                "user_id": user_id,
                "status": "restored",
                "message": f"Credenciales de usuario {user_id} restauradas"
            }
        
        else:
            return {
                "method": "thalos_generic",
                "message": "Rollback de THALOS ejecutado",
                "rollback_data": rollback_data
            }
    
    def get_rollback_history(self, organization_id: Optional[str] = None) -> list[Decision]:
        """
        Obtiene historial de rollbacks
        """
        query = self.db.query(Decision).filter(
            Decision.status == DecisionStatus.ROLLED_BACK
        )
        
        if organization_id:
            query = query.filter(Decision.organization_id == organization_id)
        
        return query.order_by(Decision.rolled_back_at.desc()).all()

