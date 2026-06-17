"""API zeus_total_system_closure_v1 — estado, auditoría y escaneo phase 2."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_superuser
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.models.zeus_closure_audit import ZeusClosureAudit
from services.zeus_bypass_scanner_v1 import run_full_audit
from services.zeus_core_guard_v1 import CRITICAL_DOMAINS, closure_active, guard_enforce

router = APIRouter(prefix="/zeus-closure/v1", tags=["zeus-closure"])


@router.get("/status")
def closure_status(
    current_user: User = Depends(get_current_active_superuser),
) -> Dict[str, Any]:
    return {
        "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED": settings.ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED,
        "ZEUS_CORE_GUARD_ENFORCE": settings.ZEUS_CORE_GUARD_ENFORCE,
        "closure_active": closure_active(),
        "guard_enforce": guard_enforce(),
        "critical_domains": sorted(CRITICAL_DOMAINS),
        "legacy_preserved": True,
        "phase_2_scanner": "services/zeus_bypass_scanner_v1.py",
        "runtime_guard": "services/zeus_runtime_guard_v1.py",
    }


@router.get("/scan")
def closure_full_scan(
    current_user: User = Depends(get_current_active_superuser),
) -> Dict[str, Any]:
    """Escaneo estático completo + auditoría de endpoints (phase 2)."""
    return run_full_audit()


@router.get("/audits")
def closure_audits(
    limit: int = 50,
    current_user: User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db),
) -> Dict[str, List[Dict[str, Any]]]:
    rows = (
        db.query(ZeusClosureAudit)
        .order_by(ZeusClosureAudit.id.desc())
        .limit(min(limit, 200))
        .all()
    )
    return {
        "audits": [
            {
                "id": r.id,
                "layer": r.layer,
                "domain": r.domain,
                "action": r.action,
                "result": r.result,
                "execution_mode": r.execution_mode,
                "human_message": r.human_message,
                "company_id": r.company_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }
