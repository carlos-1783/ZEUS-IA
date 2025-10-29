"""
ZEUS-IA - Metric Model
Métricas de rendimiento, costos y uso del sistema
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Enum
from sqlalchemy.sql import func
import enum
from backend.models.database import Base


class MetricType(str, enum.Enum):
    """Tipos de métricas"""
    # Costos
    COST_OPENAI = "cost_openai"
    COST_TOTAL = "cost_total"
    
    # Performance
    RESPONSE_TIME = "response_time"
    TOKENS_USED = "tokens_used"
    REQUESTS_COUNT = "requests_count"
    
    # Calidad
    CONFIDENCE_AVG = "confidence_avg"
    HITL_RATE = "hitl_rate"
    APPROVAL_RATE = "approval_rate"
    ERROR_RATE = "error_rate"
    
    # Agentes
    AGENT_REQUESTS = "agent_requests"
    AGENT_COST = "agent_cost"
    AGENT_SUCCESS_RATE = "agent_success_rate"
    
    # Business
    REVENUE_IMPACT = "revenue_impact"
    TIME_SAVED = "time_saved"
    ROI = "roi"
    
    # Sistema
    UPTIME = "uptime"
    ACTIVE_USERS = "active_users"


class Metric(Base):
    """
    Métrica del sistema
    Time-series data para dashboards y análisis
    """
    
    __tablename__ = "metrics"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Tipo de métrica
    metric_type = Column(Enum(MetricType), nullable=False, index=True)
    metric_name = Column(String(100), index=True)
    
    # Valor
    value = Column(Float, nullable=False)
    unit = Column(String(50))  # USD, seconds, count, percentage
    
    # Contexto
    agent_name = Column(String(50), index=True)
    user_id = Column(Integer, index=True)
    organization_id = Column(String(100), index=True)
    decision_id = Column(String(100), index=True)
    
    # Agregación
    period = Column(String(20))  # minute, hour, day, week, month
    aggregation = Column(String(20))  # sum, avg, min, max, count
    
    # Metadata
    extra_metadata = Column(JSON)
    tags = Column(JSON, default=list)
    
    # Comparación
    previous_value = Column(Float)  # Para calcular % change
    change_percentage = Column(Float)
    
    def __repr__(self):
        return f"<Metric {self.metric_name}: {self.value} {self.unit}>"
    
    def to_dict(self):
        """Convierte a diccionario"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metric_type": self.metric_type.value if self.metric_type else None,
            "metric_name": self.metric_name,
            "value": self.value,
            "unit": self.unit,
            "agent_name": self.agent_name,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "decision_id": self.decision_id,
            "period": self.period,
            "aggregation": self.aggregation,
            "extra_metadata": self.extra_metadata,
            "tags": self.tags,
            "previous_value": self.previous_value,
            "change_percentage": self.change_percentage,
        }

