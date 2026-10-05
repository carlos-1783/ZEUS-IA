"""Cola de aprobación humana para acciones críticas."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class ZeusPendingApproval(Base):
    __tablename__ = "zeus_pending_approvals"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name = Column(String(64), nullable=False)
    action_type = Column(String(64), nullable=False, index=True)
    payload_json = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="pending", index=True)  # pending|approved|executing|executed|failed|rejected
    role_required = Column(String(32), nullable=True, default="ceo")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Resultado real de la ejecucion tras la aprobacion (JSON de exito, o error si status=failed).
    result_json = Column(Text, nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    # J3b: estado unico de confirmacion. Si la solicitud nace en el chat, hilo
    # (con sufijo de usuario) y caducidad; None para solicitudes no conversacionales.
    thread_id = Column(String(128), nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
