"""
📝 Activity Logger Service
Servicio para registrar actividades de los agentes
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.agent_activity import AgentActivity
from app.db.session import SessionLocal

class ActivityLogger:
    """Servicio para registrar y consultar actividades de agentes"""
    
    @staticmethod
    def log_activity(
        agent_name: str,
        action_type: str,
        action_description: str,
        details: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        user_email: Optional[str] = None,
        status: str = "completed",
        priority: str = "normal",
        visible_to_client: bool = True
    ) -> AgentActivity:
        """
        Registrar una actividad de un agente
        
        Args:
            agent_name: Nombre del agente (ZEUS, PERSEO, etc.)
            action_type: Tipo de acción (campaign_created, invoice_sent, etc.)
            action_description: Descripción legible de la acción
            details: Detalles adicionales en JSON
            metrics: Métricas asociadas
            user_email: Email del usuario/empresa
            status: Estado (completed, failed, pending)
            priority: Prioridad (low, normal, high, critical)
            visible_to_client: Si el cliente puede ver esta actividad
            
        Returns:
            AgentActivity creada
        """
        db = SessionLocal()
        try:
            activity = AgentActivity(
                agent_name=agent_name,
                action_type=action_type,
                action_description=action_description,
                details=details,
                metrics=metrics,
                user_email=user_email,
                status=status,
                priority=priority,
                visible_to_client=visible_to_client,
                completed_at=datetime.utcnow() if status == "completed" else None
            )
            
            db.add(activity)
            db.commit()
            db.refresh(activity)
            
            print(f"[ACTIVITY] {agent_name}: {action_description}")
            
            return activity
            
        except Exception as e:
            print(f"[ERROR] Error al registrar actividad: {e}")
            db.rollback()
            return None
        finally:
            db.close()
    
    @staticmethod
    def get_agent_activities(
        agent_name: str,
        user_email: Optional[str] = None,
        limit: int = 50,
        days: int = 7
    ) -> List[AgentActivity]:
        """
        Obtener actividades de un agente
        
        Args:
            agent_name: Nombre del agente
            user_email: Filtrar por usuario específico
            limit: Número máximo de resultados
            days: Días hacia atrás
            
        Returns:
            Lista de actividades
        """
        db = SessionLocal()
        try:
            query = db.query(AgentActivity).filter(
                AgentActivity.agent_name == agent_name,
                AgentActivity.created_at >= datetime.utcnow() - timedelta(days=days)
            )
            
            if user_email:
                query = query.filter(AgentActivity.user_email == user_email)
            
            query = query.filter(AgentActivity.visible_to_client == True)
            
            activities = query.order_by(AgentActivity.created_at.desc()).limit(limit).all()
            
            return activities
            
        except Exception as e:
            print(f"[ERROR] Error al obtener actividades: {e}")
            return []
        finally:
            db.close()
    
    @staticmethod
    def get_agent_metrics(
        agent_name: str,
        user_email: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Obtener métricas agregadas de un agente
        
        Args:
            agent_name: Nombre del agente
            user_email: Filtrar por usuario
            days: Período de tiempo
            
        Returns:
            Dict con métricas agregadas
        """
        db = SessionLocal()
        try:
            query = db.query(AgentActivity).filter(
                AgentActivity.agent_name == agent_name,
                AgentActivity.created_at >= datetime.utcnow() - timedelta(days=days)
            )
            
            if user_email:
                query = query.filter(AgentActivity.user_email == user_email)
            
            activities = query.all()
            
            # Calcular métricas
            total_actions = len(activities)
            completed = len([a for a in activities if a.status == "completed"])
            failed = len([a for a in activities if a.status == "failed"])
            
            # Métricas específicas del agente
            agent_metrics = {
                "PERSEO": calculate_perseo_metrics,
                "RAFAEL": calculate_rafael_metrics,
                "THALOS": calculate_thalos_metrics,
                "JUSTICIA": calculate_justicia_metrics,
                "ZEUS": calculate_zeus_metrics
            }
            
            specific_metrics = {}
            if agent_name in agent_metrics:
                specific_metrics = agent_metrics[agent_name](activities)
            
            return {
                "agent_name": agent_name,
                "period_days": days,
                "total_actions": total_actions,
                "completed": completed,
                "failed": failed,
                "success_rate": (completed / total_actions * 100) if total_actions > 0 else 0,
                "specific_metrics": specific_metrics,
                "last_activity": activities[0].created_at.isoformat() if activities else None
            }
            
        except Exception as e:
            print(f"[ERROR] Error al calcular métricas: {e}")
            return {}
        finally:
            db.close()

# Funciones helper para métricas específicas de cada agente

def calculate_perseo_metrics(activities: List[AgentActivity]) -> Dict[str, Any]:
    """Métricas específicas de PERSEO (Marketing)"""
    campaigns_created = len([a for a in activities if a.action_type == "campaign_created"])
    optimizations = len([a for a in activities if a.action_type == "campaign_optimized"])
    
    total_roi = 0
    total_cost = 0
    
    for activity in activities:
        if activity.metrics:
            total_roi += activity.metrics.get("roi", 0)
            total_cost += activity.metrics.get("cost", 0)
    
    return {
        "campaigns_created": campaigns_created,
        "campaigns_optimized": optimizations,
        "total_ad_spend": total_cost,
        "average_roi": (total_roi / len(activities)) if activities else 0
    }

def calculate_rafael_metrics(activities: List[AgentActivity]) -> Dict[str, Any]:
    """Métricas específicas de RAFAEL (Fiscal)"""
    invoices_sent = len([a for a in activities if a.action_type == "invoice_sent"])
    models_filed = len([a for a in activities if a.action_type.startswith("modelo_")])
    
    total_invoiced = 0
    total_tax = 0
    
    for activity in activities:
        if activity.metrics:
            total_invoiced += activity.metrics.get("amount", 0)
            total_tax += activity.metrics.get("tax", 0)
    
    return {
        "invoices_sent": invoices_sent,
        "tax_models_filed": models_filed,
        "total_invoiced": total_invoiced,
        "total_tax": total_tax
    }

def calculate_thalos_metrics(activities: List[AgentActivity]) -> Dict[str, Any]:
    """Métricas específicas de THALOS (Seguridad)"""
    threats_blocked = len([a for a in activities if a.action_type == "threat_blocked"])
    scans_completed = len([a for a in activities if a.action_type == "security_scan"])
    backups_made = len([a for a in activities if a.action_type == "backup_created"])
    
    return {
        "threats_blocked": threats_blocked,
        "security_scans": scans_completed,
        "backups_created": backups_made,
        "incidents": len([a for a in activities if a.priority == "critical"])
    }

def calculate_justicia_metrics(activities: List[AgentActivity]) -> Dict[str, Any]:
    """Métricas específicas de JUSTICIA (Legal)"""
    docs_reviewed = len([a for a in activities if a.action_type == "document_reviewed"])
    compliance_checks = len([a for a in activities if a.action_type == "compliance_check"])
    
    return {
        "documents_reviewed": docs_reviewed,
        "compliance_checks": compliance_checks,
        "legal_issues": len([a for a in activities if a.status == "failed"])
    }

def calculate_zeus_metrics(activities: List[AgentActivity]) -> Dict[str, Any]:
    """Métricas específicas de ZEUS (Orquestador)"""
    tasks_delegated = len([a for a in activities if a.action_type == "task_delegated"])
    coordinations = len([a for a in activities if a.action_type == "coordination"])
    
    return {
        "tasks_delegated": tasks_delegated,
        "coordinations": coordinations,
        "efficiency": 94  # Placeholder - calcular real
    }


# Instancia global
activity_logger = ActivityLogger()

