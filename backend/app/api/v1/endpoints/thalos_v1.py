"""THALOS v1 API — monitorización y ejecución detrás de feature flags."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.db.session import get_db
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from services.thalos_executor import execute_action
from services.thalos_monitoring_service import run_monitoring_cycle

router = APIRouter(prefix="/thalos/v1", tags=["thalos-v1"])


class ThalosExecuteRequest(BaseModel):
    action: str = Field(..., description="detect_suspicious_activity|block_user|trigger_backup|alert_admin|audit_cashflow_anomaly")
    company_id: Optional[int] = None
    user_email: Optional[str] = None
    hours: int = 24
    payload: Optional[Dict[str, Any]] = None


class ThalosMonitorRequest(BaseModel):
    company_id: Optional[int] = None
    auto_execute: bool = False


@router.get("/status")
def thalos_v1_status(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return {
        "THALOS_EXECUTION_ENABLED": settings.THALOS_EXECUTION_ENABLED,
        "THALOS_AUTO_BLOCK": settings.THALOS_AUTO_BLOCK,
        "THALOS_REAL_MONITORING": settings.THALOS_REAL_MONITORING,
        "legacy_preserved": True,
    }


@router.post("/monitor")
def thalos_v1_monitor(
    body: ThalosMonitorRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return run_monitoring_cycle(
        db,
        company_id=body.company_id,
        auto_execute=body.auto_execute,
    )


@router.post("/execute")
def thalos_v1_execute(
    body: ThalosExecuteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if not settings.THALOS_EXECUTION_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="THALOS_EXECUTION_ENABLED=false. Enable flag for real execution.",
        )
    result = execute_action(
        db,
        body.action,
        company_id=body.company_id,
        user_email=body.user_email,
        hours=body.hours,
        payload=body.payload,
    )
    db.commit()
    return result


@router.get("/events")
def thalos_v1_events(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, List[Dict[str, Any]]]:
    rows = (
        db.query(ThalosSecurityEvent)
        .order_by(ThalosSecurityEvent.id.desc())
        .limit(min(limit, 200))
        .all()
    )
    return {
        "events": [
            {
                "id": r.id,
                "event_type": r.event_type,
                "severity": r.severity,
                "source": r.source,
                "user_email": r.user_email,
                "ip_address": r.ip_address,
                "company_id": r.company_id,
                "action_taken": r.action_taken,
                "decision_rule": r.decision_rule,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }
