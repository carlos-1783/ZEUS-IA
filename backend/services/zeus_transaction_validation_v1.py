"""Pre-execution validation for ZEUS transactions."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.user import User
from services.zeus_execution_controller_v1 import get_execution_status


def validate_transaction(
    db: Session,
    user: User,
    *,
    steps: List[Dict[str, Any]],
) -> Dict[str, Any]:
    execution = get_execution_status(db)
    mode = execution["execution_mode"]
    writes_on = bool(execution["writes_enabled"])
    errors: List[str] = []

    if mode == "ERROR":
        errors.append("execution_mode is ERROR — database unavailable")
    if not writes_on:
        errors.append("writes_enabled is false")

    modules = [(s.get("module") or "").upper() for s in steps]
    has_ops = "OPS" in modules
    has_rrhh = "RRHH" in modules
    has_workspace = "WORKSPACE" in modules

    if has_ops and not has_rrhh:
        rrhh_ok = _user_has_rrhh_context(db, user)
        if not rrhh_ok:
            errors.append("RRHH must exist before OPS write (no RRHH step and no employees)")

    if has_workspace:
        ops_idx = next((i for i, m in enumerate(modules) if m == "OPS"), -1)
        ws_idx = next((i for i, m in enumerate(modules) if m == "WORKSPACE"), -1)
        if ops_idx >= 0 and ws_idx >= 0 and ws_idx < ops_idx:
            errors.append("WORKSPACE step must come after OPS steps")

    for step in steps:
        module = (step.get("module") or "").upper()
        action = step.get("action") or ""
        if module == "WORKSPACE" and action not in ("persist_playbook", "persist_summary"):
            errors.append(f"Unknown WORKSPACE action: {action}")
        if module == "PERSEO" and action not in (
            "video_edit",
            "generate_image",
            "generate_video",
            "analyze_image",
            "recommend_video",
            "seo_audit",
            "generate_ads",
            "create_campaign",
            "publish_post",
            "run_pipeline",
        ):
            errors.append(f"Unknown PERSEO action: {action}")
        if module == "STORAGE" and action not in ("store_object",):
            errors.append(f"Unknown STORAGE action: {action}")

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "execution_mode": mode,
        "writes_enabled": writes_on,
    }


def _user_has_rrhh_context(db: Session, user: User) -> bool:
    try:
        from app.models.company_employee import CompanyEmployee

        count = (
            db.query(CompanyEmployee)
            .filter(CompanyEmployee.user_id == user.id, CompanyEmployee.is_active.is_(True))
            .count()
        )
        return int(count) > 0 if isinstance(count, int) else False
    except Exception:
        return False
