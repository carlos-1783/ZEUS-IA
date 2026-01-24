"""
Agent memory models: operational state, decision log.
Identity keys: company_id, agent_id, thread_id.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.db.base import Base


class AgentOperationalState(Base):
    """Operational state per agent/thread. Persisted in Postgres."""
    __tablename__ = "agent_operational_state"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(String(64), nullable=False, index=True, default="default")
    agent_id = Column(String(64), nullable=False, index=True)
    thread_id = Column(String(128), nullable=False, index=True)

    current_task = Column(Text, nullable=True)
    status = Column(String(32), nullable=True)  # idle, in_progress, blocked, completed
    next_action = Column(Text, nullable=True)
    artifacts = Column(JSON, nullable=True)  # paths, ids, refs
    blocked = Column(JSON, nullable=True)  # reason, since

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AgentDecisionLog(Base):
    """Immutable decision log. Append-only."""
    __tablename__ = "agent_decision_log"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(String(64), nullable=False, index=True, default="default")
    agent_id = Column(String(64), nullable=False, index=True)
    thread_id = Column(String(128), nullable=False, index=True)

    decision_type = Column(String(64), nullable=False)  # chat_response, workspace_execution, tool_call
    payload = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentShortTermBuffer(Base):
    """Conversation buffer (short-term). TTL 6h. Fallback when Redis not used."""
    __tablename__ = "agent_short_term_buffer"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(String(64), nullable=False, index=True, default="default")
    agent_id = Column(String(64), nullable=False, index=True)
    thread_id = Column(String(128), nullable=False, index=True)

    messages = Column(JSON, nullable=False)  # [{"role":"user"|"assistant","content":"..."}]
    expires_at = Column(DateTime(timezone=True), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
