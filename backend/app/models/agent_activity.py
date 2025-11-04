"""
📊 Agent Activity Model
Registro de actividades de cada agente IA
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean
from sqlalchemy.sql import func
from app.db.base_class import Base

class AgentActivity(Base):
    """Modelo para registrar actividades de los agentes"""
    __tablename__ = "agent_activities"

    id = Column(Integer, primary_key=True, index=True)
    
    # Agente que realizó la acción
    agent_name = Column(String, nullable=False, index=True)  # ZEUS, PERSEO, RAFAEL, etc.
    
    # Tipo de acción
    action_type = Column(String, nullable=False, index=True)  # campaign_created, invoice_sent, etc.
    
    # Descripción de la acción
    action_description = Column(Text, nullable=False)
    
    # Detalles adicionales en JSON
    details = Column(JSON, nullable=True)
    
    # Estado de la acción
    status = Column(String, default="completed")  # completed, failed, pending
    
    # Métricas asociadas
    metrics = Column(JSON, nullable=True)  # { "roi": 4.2, "cost": 250, etc. }
    
    # Usuario/empresa asociada (opcional)
    user_email = Column(String, nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Prioridad/importancia
    priority = Column(String, default="normal")  # low, normal, high, critical
    
    # Visible al cliente
    visible_to_client = Column(Boolean, default=True)

    def __repr__(self):
        return f"<AgentActivity {self.agent_name}: {self.action_type}>"

