"""THALOS v1 automation handlers — paralelos a handlers/thalos.py legacy."""

from __future__ import annotations

from typing import Any, Dict

from app.models.agent_activity import AgentActivity
from app.db.session import SessionLocal
from services.thalos_executor import execute_action
from services.thalos_monitoring_service import run_monitoring_cycle
from services.thalos_workspace_writer_v1 import write_for_activity


def _payload(activity: AgentActivity) -> Dict[str, Any]:
    return dict(activity.details or {})


def _is_superuser_email(db, email: Any) -> bool:
    """Mitigación interina (AUDIT_FIX_THALOS_SHIELD.md, sección 13).

    Estos handlers se ejecutan de forma asíncrona, fuera de una petición HTTP
    (disparados por `services/automation/agent_executor.py` sobre cualquier
    `AgentActivity` en estado `pending`/`in_progress`), así que no hay un
    `current_user` de FastAPI disponible aquí. Se re-verifica en BD que el
    `user_email` de la actividad (ahora forzado server-side por
    `app/api/v1/endpoints/activities.py::log_activity`, no confiable si la
    actividad fue creada por otra vía) pertenezca de verdad a un
    superusuario, replicando el mismo gate ya aplicado a los endpoints
    síncronos equivalentes (`POST /thalos/v1/execute` con
    `detect_suspicious_activity`, `POST /thalos/v1/monitor`).
    """
    if not email:
        return False
    from sqlalchemy import func

    from app.models.user import User

    user = db.query(User).filter(func.lower(User.email) == str(email).strip().lower()).first()
    return bool(user and getattr(user, "is_superuser", False))


def _blocked_superuser_required(action: str) -> Dict[str, Any]:
    return {
        "status": "blocked",
        "details_update": {
            "thalos_v1": {
                "status": "blocked",
                "action": action,
                "executed": False,
                "reason": "superuser_required_for_global_audit",
            }
        },
        "metrics_update": {"thalos_v1_executed": 0},
        "notes": (
            f"THALOS v1 {action}: bloqueado, requiere superusuario "
            "(mitigación interina, ver AUDIT_FIX_THALOS_SHIELD.md sección 13)."
        ),
    }


def _wrap_result(activity: AgentActivity, result: Dict[str, Any]) -> Dict[str, Any]:
    executed = bool(result.get("executed"))
    status = "completed" if result.get("status") != "error" else "failed"
    return {
        "status": status,
        "details_update": {"thalos_v1": result},
        "metrics_update": {"thalos_v1_executed": 1 if executed else 0},
        "notes": f"THALOS v1 {result.get('action', activity.action_type)}: {result.get('status')}",
    }


def handle_thalos_v1_detect(activity: AgentActivity) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        if not _is_superuser_email(db, activity.user_email):
            return _blocked_superuser_required("detect_suspicious_activity")
        p = _payload(activity)
        result = execute_action(
            db,
            "detect_suspicious_activity",
            hours=int(p.get("hours", 24)),
            company_id=p.get("company_id"),
        )
        write_for_activity(db, activity, action="detect_suspicious_activity", result=result)
        db.commit()
        return _wrap_result(activity, result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def handle_thalos_v1_cashflow(activity: AgentActivity) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        if not _is_superuser_email(db, activity.user_email):
            return _blocked_superuser_required("audit_cashflow_anomaly")
        p = _payload(activity)
        result = execute_action(
            db,
            "audit_cashflow_anomaly",
            company_id=p.get("company_id"),
            payload=p,
        )
        write_for_activity(db, activity, action="audit_cashflow_anomaly", result=result)
        db.commit()
        return _wrap_result(activity, result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def handle_thalos_v1_backup(activity: AgentActivity) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        if not _is_superuser_email(db, activity.user_email):
            return _blocked_superuser_required("trigger_backup")
        result = execute_action(db, "trigger_backup")
        write_for_activity(db, activity, action="trigger_backup", result=result)
        db.commit()
        return _wrap_result(activity, result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def handle_thalos_v1_block(activity: AgentActivity) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        if not _is_superuser_email(db, activity.user_email):
            return _blocked_superuser_required("block_user")
        p = _payload(activity)
        result = execute_action(
            db,
            "block_user",
            user_email=p.get("email") or p.get("user_email"),
            company_id=p.get("company_id"),
            payload=p,
        )
        write_for_activity(db, activity, action="block_user", result=result)
        db.commit()
        return _wrap_result(activity, result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def handle_thalos_v1_alert(activity: AgentActivity) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        if not _is_superuser_email(db, activity.user_email):
            return _blocked_superuser_required("alert_admin")
        p = _payload(activity)
        result = execute_action(
            db,
            "alert_admin",
            company_id=p.get("company_id"),
            payload=p,
        )
        write_for_activity(db, activity, action="alert_admin", result=result)
        db.commit()
        return _wrap_result(activity, result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def handle_thalos_v1_monitor(activity: AgentActivity) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        if not _is_superuser_email(db, activity.user_email):
            return _blocked_superuser_required("security_monitor")
        p = _payload(activity)
        cycle = run_monitoring_cycle(
            db,
            company_id=p.get("company_id"),
            auto_execute=bool(p.get("auto_execute")),
            force_scan=True,
        )
        write_for_activity(
            db,
            activity,
            action="security_monitor",
            result={"status": "completed", "executed": True, "result": cycle},
        )
        db.commit()
        return {
            "status": "completed",
            "details_update": {"thalos_v1_monitor": cycle},
            "metrics_update": {"rules_triggered": len(cycle.get("rules_triggered") or [])},
            "notes": "THALOS v1 monitoring cycle completed",
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
