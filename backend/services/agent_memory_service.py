"""
Agent memory service: short-term buffer, operational state, decision log.
Identity: company_id, agent_id, thread_id.
NO_RESPONSE_WITHOUT_MEMORY_WRITE: every agent interaction must persist.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.agent_memory import AgentOperationalState, AgentDecisionLog, AgentShortTermBuffer


SHORT_TERM_TTL_HOURS = 6


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_tables(session: Session) -> None:
    from app.db.base import Base, engine
    Base.metadata.create_all(bind=engine)


def load(
    company_id: str,
    agent_id: str,
    thread_id: str,
) -> Dict[str, Any]:
    """Load short-term buffer, operational state, and recent decisions."""
    session = SessionLocal()
    try:
        _ensure_tables(session)
        company_id = company_id or "default"
        agent_id = (agent_id or "").upper()
        thread_id = thread_id or "main"

        # Short-term buffer (only if not expired)
        buf = (
            session.query(AgentShortTermBuffer)
            .filter(
                AgentShortTermBuffer.company_id == company_id,
                AgentShortTermBuffer.agent_id == agent_id,
                AgentShortTermBuffer.thread_id == thread_id,
                AgentShortTermBuffer.expires_at > _utcnow(),
            )
            .first()
        )
        short_term = []
        if buf and buf.messages:
            short_term = buf.messages if isinstance(buf.messages, list) else []

        # Operational state
        state = (
            session.query(AgentOperationalState)
            .filter(
                AgentOperationalState.company_id == company_id,
                AgentOperationalState.agent_id == agent_id,
                AgentOperationalState.thread_id == thread_id,
            )
            .first()
        )
        operational = {}
        if state:
            operational = {
                "current_task": state.current_task,
                "status": state.status,
                "next_action": state.next_action,
                "artifacts": state.artifacts or {},
                "blocked": state.blocked,
            }

        # Recent decisions (last 20)
        rows = (
            session.query(AgentDecisionLog)
            .filter(
                AgentDecisionLog.company_id == company_id,
                AgentDecisionLog.agent_id == agent_id,
                AgentDecisionLog.thread_id == thread_id,
            )
            .order_by(AgentDecisionLog.created_at.desc())
            .limit(20)
            .all()
        )
        decisions = [
            {"type": r.decision_type, "payload": r.payload, "at": r.created_at.isoformat()}
            for r in reversed(rows)
        ]

        return {
            "short_term": short_term,
            "operational": operational,
            "decisions": decisions,
        }
    finally:
        session.close()


def persist_short_term(
    company_id: str,
    agent_id: str,
    thread_id: str,
    messages: List[Dict[str, str]],
) -> None:
    """Upsert conversation buffer. TTL 6h."""
    session = SessionLocal()
    try:
        _ensure_tables(session)
        company_id = company_id or "default"
        agent_id = (agent_id or "").upper()
        thread_id = thread_id or "main"
        expires = _utcnow() + timedelta(hours=SHORT_TERM_TTL_HOURS)

        row = (
            session.query(AgentShortTermBuffer)
            .filter(
                AgentShortTermBuffer.company_id == company_id,
                AgentShortTermBuffer.agent_id == agent_id,
                AgentShortTermBuffer.thread_id == thread_id,
            )
            .first()
        )
        if row:
            row.messages = messages
            row.expires_at = expires
            row.updated_at = _utcnow()
        else:
            row = AgentShortTermBuffer(
                company_id=company_id,
                agent_id=agent_id,
                thread_id=thread_id,
                messages=messages,
                expires_at=expires,
            )
            session.add(row)
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


def persist_operational_state(
    company_id: str,
    agent_id: str,
    thread_id: str,
    *,
    current_task: Optional[str] = None,
    status: Optional[str] = None,
    next_action: Optional[str] = None,
    artifacts: Optional[Dict[str, Any]] = None,
    blocked: Optional[Dict[str, Any]] = None,
) -> None:
    """Upsert operational state."""
    session = SessionLocal()
    try:
        _ensure_tables(session)
        company_id = company_id or "default"
        agent_id = (agent_id or "").upper()
        thread_id = thread_id or "main"

        row = (
            session.query(AgentOperationalState)
            .filter(
                AgentOperationalState.company_id == company_id,
                AgentOperationalState.agent_id == agent_id,
                AgentOperationalState.thread_id == thread_id,
            )
            .first()
        )
        if row:
            if current_task is not None:
                row.current_task = current_task
            if status is not None:
                row.status = status
            if next_action is not None:
                row.next_action = next_action
            if artifacts is not None:
                row.artifacts = artifacts
            if blocked is not None:
                row.blocked = blocked
            row.updated_at = _utcnow()
        else:
            row = AgentOperationalState(
                company_id=company_id,
                agent_id=agent_id,
                thread_id=thread_id,
                current_task=current_task,
                status=status,
                next_action=next_action,
                artifacts=artifacts,
                blocked=blocked,
            )
            session.add(row)
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


def append_decision_log(
    company_id: str,
    agent_id: str,
    thread_id: str,
    decision_type: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Append immutable decision log entry."""
    session = SessionLocal()
    try:
        _ensure_tables(session)
        company_id = company_id or "default"
        agent_id = (agent_id or "").upper()
        thread_id = thread_id or "main"

        row = AgentDecisionLog(
            company_id=company_id,
            agent_id=agent_id,
            thread_id=thread_id,
            decision_type=decision_type,
            payload=payload or {},
        )
        session.add(row)
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()
