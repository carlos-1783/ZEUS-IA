"""
ZEUS-IA - Metrics Service
Sistema de métricas para dashboard de costos y rendimiento
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.metric import Metric, MetricType
from backend.models.decision import Decision
from backend.models.hitl_queue import HITLQueue


class MetricsService:
    """
    Servicio de métricas
    Recopila y agrega métricas de rendimiento, costos y uso
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def record_metric(
        self,
        metric_type: MetricType,
        value: float,
        unit: str,
        agent_name: Optional[str] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        period: str = "instant",
        aggregation: str = "value",
        extra_metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Metric:
        """
        Registra una métrica
        """
        
        metric = Metric(
            metric_type=metric_type,
            metric_name=metric_type.value,
            value=value,
            unit=unit,
            agent_name=agent_name,
            user_id=user_id,
            organization_id=organization_id,
            decision_id=decision_id,
            period=period,
            aggregation=aggregation,
            extra_metadata=extra_metadata or {},
            tags=tags or []
        )
        
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        
        return metric
    
    # =============================================================================
    # COSTOS
    # =============================================================================
    
    def record_openai_cost(
        self,
        cost: float,
        tokens_used: int,
        agent_name: str,
        decision_id: Optional[str] = None,
        organization_id: Optional[str] = None
    ) -> Metric:
        """Registra costo de OpenAI"""
        return self.record_metric(
            metric_type=MetricType.COST_OPENAI,
            value=cost,
            unit="USD",
            agent_name=agent_name,
            decision_id=decision_id,
            organization_id=organization_id,
            extra_metadata={"tokens_used": tokens_used}
        )
    
    def get_total_cost(
        self,
        organization_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> float:
        """Obtiene costo total"""
        query = self.db.query(func.sum(Metric.value)).filter(
            Metric.metric_type.in_([MetricType.COST_OPENAI, MetricType.COST_TOTAL])
        )
        
        if organization_id:
            query = query.filter(Metric.organization_id == organization_id)
        
        if start_date:
            query = query.filter(Metric.timestamp >= start_date)
        
        if end_date:
            query = query.filter(Metric.timestamp <= end_date)
        
        result = query.scalar()
        return float(result) if result else 0.0
    
    def get_cost_by_agent(
        self,
        organization_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, float]:
        """Costo por agente en últimos N días"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        results = self.db.query(
            Metric.agent_name,
            func.sum(Metric.value).label("total_cost")
        ).filter(
            Metric.metric_type == MetricType.COST_OPENAI,
            Metric.timestamp >= start_date
        )
        
        if organization_id:
            results = results.filter(Metric.organization_id == organization_id)
        
        results = results.group_by(Metric.agent_name).all()
        
        return {agent: float(cost) for agent, cost in results if agent}
    
    # =============================================================================
    # RENDIMIENTO
    # =============================================================================
    
    def record_response_time(
        self,
        response_time: float,
        agent_name: str,
        decision_id: Optional[str] = None
    ) -> Metric:
        """Registra tiempo de respuesta"""
        return self.record_metric(
            metric_type=MetricType.RESPONSE_TIME,
            value=response_time,
            unit="seconds",
            agent_name=agent_name,
            decision_id=decision_id
        )
    
    def get_avg_response_time(
        self,
        agent_name: Optional[str] = None,
        days: int = 7
    ) -> float:
        """Tiempo de respuesta promedio"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(func.avg(Metric.value)).filter(
            Metric.metric_type == MetricType.RESPONSE_TIME,
            Metric.timestamp >= start_date
        )
        
        if agent_name:
            query = query.filter(Metric.agent_name == agent_name)
        
        result = query.scalar()
        return float(result) if result else 0.0
    
    # =============================================================================
    # CALIDAD
    # =============================================================================
    
    def calculate_hitl_rate(
        self,
        organization_id: Optional[str] = None,
        days: int = 30
    ) -> float:
        """
        Calcula tasa de HITL (% de decisiones que requirieron aprobación humana)
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Total decisiones
        total_query = self.db.query(func.count(Decision.id)).filter(
            Decision.created_at >= start_date
        )
        
        if organization_id:
            total_query = total_query.filter(Decision.organization_id == organization_id)
        
        total = total_query.scalar() or 0
        
        if total == 0:
            return 0.0
        
        # Decisiones que requirieron HITL
        hitl_query = self.db.query(func.count(Decision.id)).filter(
            Decision.created_at >= start_date,
            Decision.hitl_required == True
        )
        
        if organization_id:
            hitl_query = hitl_query.filter(Decision.organization_id == organization_id)
        
        hitl_count = hitl_query.scalar() or 0
        
        hitl_rate = (hitl_count / total) * 100
        
        # Registrar métrica
        self.record_metric(
            metric_type=MetricType.HITL_RATE,
            value=hitl_rate,
            unit="percentage",
            organization_id=organization_id,
            period="day",
            aggregation="avg"
        )
        
        return hitl_rate
    
    def calculate_approval_rate(
        self,
        organization_id: Optional[str] = None,
        days: int = 30
    ) -> float:
        """
        Calcula tasa de aprobación (% de HITLs aprobados vs rechazados)
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Total HITLs resueltos
        total_query = self.db.query(func.count(HITLQueue.id)).filter(
            HITLQueue.created_at >= start_date,
            HITLQueue.status.in_(["approved", "rejected"])
        )
        
        if organization_id:
            total_query = total_query.filter(HITLQueue.organization_id == organization_id)
        
        total = total_query.scalar() or 0
        
        if total == 0:
            return 0.0
        
        # HITLs aprobados
        approved_query = self.db.query(func.count(HITLQueue.id)).filter(
            HITLQueue.created_at >= start_date,
            HITLQueue.status == "approved"
        )
        
        if organization_id:
            approved_query = approved_query.filter(HITLQueue.organization_id == organization_id)
        
        approved = approved_query.scalar() or 0
        
        approval_rate = (approved / total) * 100
        
        # Registrar métrica
        self.record_metric(
            metric_type=MetricType.APPROVAL_RATE,
            value=approval_rate,
            unit="percentage",
            organization_id=organization_id,
            period="day",
            aggregation="avg"
        )
        
        return approval_rate
    
    # =============================================================================
    # DASHBOARD COMPLETO
    # =============================================================================
    
    def get_dashboard_metrics(
        self,
        organization_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Obtiene todas las métricas para el dashboard
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Costos
        total_cost = self.get_total_cost(organization_id, start_date)
        cost_by_agent = self.get_cost_by_agent(organization_id, days)
        
        # Decisiones
        total_decisions = self.db.query(func.count(Decision.id)).filter(
            Decision.created_at >= start_date
        )
        if organization_id:
            total_decisions = total_decisions.filter(Decision.organization_id == organization_id)
        total_decisions = total_decisions.scalar() or 0
        
        # Rendimiento
        avg_response_time = self.get_avg_response_time(None, days)
        
        # Calidad
        hitl_rate = self.calculate_hitl_rate(organization_id, days)
        approval_rate = self.calculate_approval_rate(organization_id, days)
        
        # Actividad por agente
        agent_stats = {}
        for agent_name in ["PERSEO", "RAFAEL", "ZEUS CORE", "THALOS", "JUSTICIA"]:
            agent_decisions = self.db.query(func.count(Decision.id)).filter(
                Decision.agent_name == agent_name,
                Decision.created_at >= start_date
            )
            if organization_id:
                agent_decisions = agent_decisions.filter(Decision.organization_id == organization_id)
            
            count = agent_decisions.scalar() or 0
            cost = cost_by_agent.get(agent_name, 0.0)
            
            agent_stats[agent_name] = {
                "requests": count,
                "cost": cost,
                "avg_cost_per_request": cost / count if count > 0 else 0.0
            }
        
        return {
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "costs": {
                "total": total_cost,
                "by_agent": cost_by_agent,
                "avg_per_decision": total_cost / total_decisions if total_decisions > 0 else 0.0
            },
            "performance": {
                "total_decisions": total_decisions,
                "avg_response_time": avg_response_time,
                "decisions_per_day": total_decisions / days if days > 0 else 0
            },
            "quality": {
                "hitl_rate": hitl_rate,
                "approval_rate": approval_rate
            },
            "agents": agent_stats
        }

