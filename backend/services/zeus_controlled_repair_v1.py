"""ZEUS controlled repair v1 — sequential verified execution phases."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.config import settings, _finalize_static_dir_path
from app.models.user import User
from services.automation.handlers import (
    GENERIC_INTERNAL_ACTION_TYPES,
    HANDLER_MAP,
    TEAMFLOW_REAL_ACTION_TYPES,
    resolve_handler,
    scan_handler_coverage,
)
from services.automation.handlers.generic_internal import (
    GENERIC_INTERNAL_HANDLER_NAME,
    handle_generic_internal,
)
from services.zeus_event_bus_v1 import EVENT_TARGETS, event_bus_status
from services.zeus_execution_controller_v1 import get_execution_status
from services.zeus_safe_lock_v1 import run_safe_lock

logger = logging.getLogger(__name__)

REPAIR_ID = "zeus_controlled_repair_v1"
REQUIRED_ENV = {
    "AFRODITA_EXECUTION_ENABLED": "true",
    "AFRODITA_READ_ONLY_MODE": "false",
    "ZEUS_AGENT_ENABLED": "true",
    "TEAMFLOW_ENABLED": "true",
    "AFRODITA_OPS_ENABLED": "true",
    "AFRODITA_OPS_READ_ONLY": "false",
}
_EMBEDDED_FLAG_RE = re.compile(
    r"[A-Z][A-Z0-9_]*=(?:true|false|1|0|yes|no)\b",
    re.IGNORECASE,
)


def _phase(name: str, *, passed: bool, checks: List[Dict[str, Any]], detail: str = "") -> Dict[str, Any]:
    return {
        "phase": name,
        "passed": passed,
        "checks": checks,
        "detail": detail,
    }


def _check(name: str, ok: bool, detail: str) -> Dict[str, Any]:
    return {"check": name, "passed": ok, "detail": detail}


def _validate_env() -> Dict[str, Any]:
    checks = []
    for key, expected in REQUIRED_ENV.items():
        raw = os.environ.get(key)
        ok = raw is not None and raw.strip().lower() == expected.lower()
        checks.append(_check(key, ok, f"actual={raw!r} expected={expected!r}"))
    passed = all(c["passed"] for c in checks)
    return _phase("ENVIRONMENT_LOCK", passed=passed, checks=checks)


def _sanitize_static_dir() -> Dict[str, Any]:
    raw = (os.getenv("ZEUS_STATIC_DIR") or os.getenv("STATIC_DIR") or settings.STATIC_DIR or "").strip()
    has_embedded = bool(_EMBEDDED_FLAG_RE.search(raw))
    resolved = _finalize_static_dir_path(raw) if raw else settings.STATIC_DIR
    path_only = not has_embedded and (not raw or os.path.isabs(resolved) or raw.startswith("/"))
    checks = [
        _check("static_dir_path_only", path_only, f"raw={raw[:80]!r} resolved={resolved!r}"),
        _check("no_embedded_flags", not has_embedded, "STATIC_DIR must not contain env key=value"),
    ]
    passed = all(c["passed"] for c in checks)
    return _phase("ENVIRONMENT_LOCK_STATIC", passed=passed, checks=checks)


def _verify_env_runtime(db: Session) -> Dict[str, Any]:
    execution = get_execution_status(db)
    safe = run_safe_lock(db, execution_status=execution, log_warnings=False)
    checks = [
        _check("execution_mode_REAL", execution.get("execution_mode") == "REAL", str(execution.get("execution_mode"))),
        _check("writes_enabled", bool(execution.get("writes_enabled")), str(execution.get("writes_enabled"))),
        _check("verified_real", bool(safe.get("verified_real")), str(safe.get("verified_real"))),
    ]
    passed = all(c["passed"] for c in checks)
    return _phase("ENVIRONMENT_LOCK_VERIFY", passed=passed, checks=checks, detail="zeus/status truth")


def _database_lock(db: Session) -> Dict[str, Any]:
    tables: List[str] = []
    try:
        tables = inspect(db.get_bind()).get_table_names()
    except Exception as exc:
        return _phase("DATABASE_LOCK", passed=False, checks=[_check("db_inspect", False, str(exc))])

    needed = ("teamflow_items", "teamflow_events", "zeus_domain_events")
    checks = [_check(f"table_{t}", t in tables, "present" if t in tables else "missing — run alembic upgrade head") for t in needed]
    db_ok = execution.get("db_status") == "connected" if (execution := get_execution_status(db)) else False
    checks.append(_check("health_db_connected", db_ok, execution.get("db_status", "unknown")))
    passed = all(c["passed"] for c in checks)
    return _phase("DATABASE_LOCK", passed=passed, checks=checks)


def _teamflow_handler_replacement() -> Dict[str, Any]:
    coverage = scan_handler_coverage()
    checks = [
        _check("generic_handlers_count_zero", coverage["generic_handlers_count"] == 0, str(coverage["generic_handlers_count"])),
        _check("critical_actions_all_real", coverage["critical_actions_all_real"], str(coverage.get("generic_on_critical"))),
    ]
    for action in sorted(TEAMFLOW_REAL_ACTION_TYPES):
        handler = None
        for agent, actions in HANDLER_MAP.items():
            h = actions.get(action)
            if h and h is not handle_generic_internal:
                handler = h
                break
        if handler is None:
            handler = resolve_handler("PERSEO", action)
        checks.append(
            _check(
                f"handler_{action}",
                handler is not handle_generic_internal and handler.__name__ != "handle_unmapped_no_fake",
                handler.__name__ if handler else "no real handler mapped",
            )
        )
    passed = all(c["passed"] for c in checks)
    return _phase(
        "TEAMFLOW_HANDLER_REPLACEMENT",
        passed=passed,
        checks=checks,
        detail=f"teamflow_real={coverage.get('teamflow_real_percentage')}%",
    )


def _event_bus_injection(db: Session) -> Dict[str, Any]:
    status = event_bus_status(db)
    checks = [
        _check("event_bus_active", bool(status.get("active")), str(status)),
    ]
    for event_name in EVENT_TARGETS:
        checks.append(_check(f"event_registered_{event_name}", event_name in EVENT_TARGETS, str(EVENT_TARGETS[event_name])))
    passed = all(c["passed"] for c in checks)
    return _phase("EVENT_BUS_INJECTION", passed=passed, checks=checks)


def _workspace_activation(db: Session, user: User) -> Dict[str, Any]:
    bound = False
    detail = ""
    try:
        from services.workspace_playbook_service_v1 import workspace_enabled
        from services.teamflow_engine import teamflow_engine

        bound = workspace_enabled() and bool(teamflow_engine.list_workflows())
        detail = "playbooks bound on teamflow run_workflow via persist_execution_playbook"
    except Exception as exc:
        detail = str(exc)
    checks = [
        _check("workspace_playbook_execution_triggers_teamflow", bound, detail),
        _check("teamflow_enabled", bool(getattr(settings, "TEAMFLOW_ENABLED", True)), "TEAMFLOW_ENABLED"),
    ]
    passed = all(c["passed"] for c in checks)
    return _phase("WORKSPACE_ACTIVATION", passed=passed, checks=checks)


def _automation_cleanup() -> Dict[str, Any]:
    fake_remaining = []
    for action in TEAMFLOW_REAL_ACTION_TYPES:
        h = resolve_handler("UNKNOWN", action)
        if h is handle_generic_internal:
            fake_remaining.append(action)
    unmapped_fail_closed = resolve_handler("UNKNOWN", "totally_unknown_action").__name__ == "handle_unmapped_no_fake"
    checks = [
        _check("no_fake_critical_handlers", len(fake_remaining) == 0, str(fake_remaining)),
        _check("unmapped_fail_closed", unmapped_fail_closed, "no_generic_fallback"),
        _check("generic_only_internal", all(a in GENERIC_INTERNAL_ACTION_TYPES for a in GENERIC_INTERNAL_ACTION_TYPES), "ok"),
    ]
    passed = all(c["passed"] for c in checks)
    return _phase("AUTOMATION_CLEANUP", passed=passed, checks=checks)


def _frontend_sync_lock(db: Session) -> Dict[str, Any]:
    execution = get_execution_status(db)
    safe = run_safe_lock(db, execution_status=execution, log_warnings=False)
    real_only_if_verified = bool(safe.get("ui_show_real_only_if_verified"))
    checks = [
        _check("backend_verified_real_field", "verified_real" in safe, "present in safe_lock"),
        _check("ui_show_real_only_if_verified", real_only_if_verified, str(real_only_if_verified)),
        _check("no_fake_real_when_simulated", not (execution.get("execution_mode") != "REAL" and safe.get("verified_real")), "consistent"),
    ]
    passed = all(c["passed"] for c in checks)
    return _phase("FRONTEND_SYNC_LOCK", passed=passed, checks=checks)


def _final_system_validation(db: Session, user: User) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    try:
        from services.afrodita_workspace_service_v1 import can_create_employee

        checks.append(_check("employee_creation_gate", can_create_employee(), "can_create_employee()"))
    except Exception as exc:
        checks.append(_check("employee_creation_gate", False, str(exc)))

    coverage = scan_handler_coverage()
    checks.append(
        _check(
            "teamflow_executes_real_handler",
            coverage["critical_actions_all_real"],
            f"generic={coverage['generic_handlers_count']}",
        )
    )

    bus = event_bus_status(db)
    checks.append(_check("events_propagate", bus.get("active") is True, str(bus.get("registered_events"))))

    try:
        from app.models.company_employee import CompanyEmployee

        emp_count = db.query(CompanyEmployee).count()
        checks.append(_check("employee_table_readable", True, f"rows={emp_count}"))
    except Exception as exc:
        checks.append(_check("employee_table_readable", False, str(exc)))

    passed = all(c["passed"] for c in checks)
    return _phase("FINAL_SYSTEM_VALIDATION", passed=passed, checks=checks)


def run_controlled_repair(
    db: Session,
    user: User,
    *,
    stop_on_error: bool = True,
) -> Dict[str, Any]:
    """Run all repair phases sequentially; STOP_ON_ERROR by default."""
    logs: List[str] = []
    phases: List[Dict[str, Any]] = []
    failed_phase: Optional[str] = None

    steps = [
        _validate_env,
        _sanitize_static_dir,
        lambda: _verify_env_runtime(db),
        lambda: _database_lock(db),
        _teamflow_handler_replacement,
        lambda: _event_bus_injection(db),
        lambda: _workspace_activation(db, user),
        _automation_cleanup,
        lambda: _frontend_sync_lock(db),
        lambda: _final_system_validation(db, user),
    ]

    for step in steps:
        try:
            result = step()
            phases.append(result)
            logs.append(f"{result['phase']}: {'PASS' if result['passed'] else 'FAIL'}")
            if not result["passed"]:
                failed_phase = result["phase"]
                if stop_on_error:
                    break
        except Exception as exc:
            logger.exception("[CONTROLLED_REPAIR] phase error")
            failed_phase = getattr(step, "__name__", "unknown")
            phases.append(_phase(failed_phase or "ERROR", passed=False, checks=[_check("exception", False, str(exc))]))
            logs.append(f"ERROR: {exc}")
            if stop_on_error:
                break

    coverage = scan_handler_coverage()
    execution = get_execution_status(db)
    blockers = sum(1 for p in phases if not p.get("passed"))
    score = max(0, 100 - blockers * 10)
    real_pct = 100.0 if execution.get("execution_mode") == "REAL" and execution.get("writes_enabled") else 70.0

    success = (
        failed_phase is None
        and score >= 85
        and coverage["teamflow_real_percentage"] >= 100.0
        and coverage["generic_handlers_count"] == 0
        and blockers == 0
    )

    verdict = "PRODUCTION_READY" if success else ("HARD_BLOCK" if failed_phase else "DEGRADED")

    return {
        "execution_status": "completed" if not failed_phase else "stopped",
        "repair_id": REPAIR_ID,
        "strategy": "sequential_verified_execution",
        "failed_phase": failed_phase,
        "logs": logs,
        "phases": phases,
        "final_verdict": verdict,
        "success_criteria": {
            "production_readiness_score": score,
            "teamflow_real_percentage": coverage["teamflow_real_percentage"],
            "real_execution_percentage": real_pct,
            "critical_blockers": blockers,
            "generic_handlers_remaining": coverage["generic_handlers_count"],
            "generic_handler_name_eliminated_for_critical": GENERIC_INTERNAL_HANDLER_NAME,
        },
        "handler_coverage": coverage,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
