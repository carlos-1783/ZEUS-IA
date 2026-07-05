"""Read-only automation audit logs — observability without execution changes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.zeus_analytics import ZeusAutomationLog

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def record_automation_audit(
    db: Session,
    *,
    automation_name: str,
    agent: str = "unknown",
    trigger_type: str = "manual",
    status: str = "success",
    input_data: Optional[Dict[str, Any]] = None,
    output_data: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
) -> Optional[str]:
    """Append one automation execution log (best-effort, non-blocking)."""
    try:
        row = ZeusAutomationLog(
            automation_name=(automation_name or "unknown")[:128],
            agent=(agent or "unknown")[:64],
            trigger_type=(trigger_type or "manual")[:32],
            status=(status or "unknown")[:32],
            input_data=input_data,
            output_data=output_data,
            user_id=user_id,
            executed_at=_utcnow(),
        )
        db.add(row)
        db.flush()
        return row.id
    except Exception as exc:
        logger.warning("[AUTOMATION_AUDIT] record failed: %s", exc)
        return None


def get_automation_audit(
    db: Session,
    user: Optional[User],
    *,
    limit: int = 100,
) -> Dict[str, Any]:
    """Recent logs + per-automation summary (read-only)."""
    limit = min(max(limit, 1), 500)
    try:
        q = db.query(ZeusAutomationLog)
        if user and not getattr(user, "is_superuser", False):
            q = q.filter(ZeusAutomationLog.user_id == user.id)
        logs = q.order_by(ZeusAutomationLog.executed_at.desc()).limit(limit).all()

        sq = db.query(
            ZeusAutomationLog.automation_name.label("automation_name"),
            func.count(ZeusAutomationLog.id).label("total_runs"),
            func.max(ZeusAutomationLog.executed_at).label("last_run"),
        )
        if user and not getattr(user, "is_superuser", False):
            sq = sq.filter(ZeusAutomationLog.user_id == user.id)
        summary_rows = (
            sq.group_by(ZeusAutomationLog.automation_name)
            .order_by(func.max(ZeusAutomationLog.executed_at).desc())
            .all()
        )

        return {
            "success": True,
            "read_only": True,
            "logs": [
                {
                    "id": log.id,
                    "automation_name": log.automation_name,
                    "agent": log.agent,
                    "trigger_type": log.trigger_type,
                    "status": log.status,
                    "input_data": log.input_data,
                    "output_data": log.output_data,
                    "executed_at": log.executed_at.isoformat() if log.executed_at else None,
                }
                for log in logs
            ],
            "summary": [
                {
                    "automation_name": row.automation_name,
                    "total_runs": int(row.total_runs or 0),
                    "last_run": row.last_run.isoformat() if row.last_run else None,
                }
                for row in summary_rows
            ],
            "total_logs": len(logs),
        }
    except Exception as exc:
        logger.warning("[AUTOMATION_AUDIT] get failed: %s", exc)
        return {
            "success": False,
            "read_only": True,
            "logs": [],
            "summary": [],
            "error": str(exc),
        }
