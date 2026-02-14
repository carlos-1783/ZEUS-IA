"""
📊 Automation Readiness Model
Evaluación de madurez para automatización de ventas y captación.
"""
from sqlalchemy import Column, Integer, Float, Boolean, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base


class AutomationReadiness(Base):
    """Modelo para evaluaciones de readiness de automatización por empresa/usuario"""
    __tablename__ = "automation_readiness"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    leads_last_30_days = Column(Integer, default=0)
    avg_response_time_hours = Column(Float, default=0.0)
    active_channels = Column(Integer, default=0)
    monthly_revenue_estimate = Column(Float, default=0.0)
    has_defined_offer = Column(Boolean, default=False)
    has_sales_process = Column(Boolean, default=False)
    team_size = Column(Integer, default=0)

    score = Column(Integer, default=0)
    status = Column(String(50), nullable=True)

    evaluated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<AutomationReadiness company={self.company_id} score={self.score} status={self.status}>"
