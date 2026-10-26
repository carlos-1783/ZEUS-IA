"""
🛡️ THALOS Automation Handler
Procesa auditorías de seguridad, alertas y backups.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from app.db.session import SessionLocal
from app.db.rls_context import open_activity_session
from app.models.agent_activity import AgentActivity
from .. import utils
from .thalos_v1 import _is_superuser_email


def _blocked_superuser_required(action: str) -> Dict[str, Any]:
    """Mismo gate ya aplicado en thalos_v1.py (Vuelta 5/6) — Vuelta 7 lo
    extiende a las 3 acciones legacy de este archivo (`security_scan`,
    `task_assigned` -> alerts, `backup_created`), alcanzables por el mismo
    HANDLER_MAP["THALOS"] y el mismo vector asíncrono
    (POST /api/v1/activities/log -> AgentAutomationExecutor -> resolve_handler)
    que ya se cerró para sus hermanos de thalos_v1.py. Ver
    AUDIT_THALOS_ESTRUCTURAL.md sección 15.5/16.
    """
    return {
        "status": "blocked",
        "details_update": {
            "automation": {
                "status": "blocked",
                "action": action,
                "executed": False,
                "reason": "superuser_required_for_global_audit",
            }
        },
        "metrics_update": {"executed": 0},
        "notes": (
            f"THALOS {action}: bloqueado, requiere superusuario "
            "(mismo gate ya aplicado a los handlers hermanos de thalos_v1.py)."
        ),
    }


def _require_superuser(activity: AgentActivity) -> bool:
    db = open_activity_session(activity)
    try:
        return _is_superuser_email(db, activity.user_email)
    finally:
        db.close()


def handle_thalos_security_scan(activity: AgentActivity) -> Dict[str, Any]:
    if not _require_superuser(activity):
        return _blocked_superuser_required(activity.action_type or "security_scan")

    checks = {
        "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
        "STRIPE_API_KEY": bool(os.getenv("STRIPE_API_KEY")),
        "STRIPE_MODE": os.getenv("STRIPE_MODE", "auto"),
        "SENDGRID_API_KEY": bool(os.getenv("SENDGRID_API_KEY")),
        "TWILIO_ACCOUNT_SID": bool(os.getenv("TWILIO_ACCOUNT_SID")),
    }
    missing = [key for key, value in checks.items() if isinstance(value, bool) and not value]

    payload = {
        "executed_at": datetime.utcnow().isoformat(),
        "checks": checks,
        "missing": missing,
        "recommendations": "Actualizar credenciales faltantes en Railway." if missing else "Todas las variables críticas configuradas.",
    }

    prefix = f"{activity.id}_{activity.action_type}"
    json_path = utils.write_json("THALOS", prefix, payload, company_id=activity.company_id)
    utils.write_log("THALOS", prefix, payload)

    notes = f"Auditoría ejecutada automáticamente. Informe: {json_path}"
    status = "failed" if missing else "completed"

    return {
        "status": status,
        "details_update": {"automation": {"deliverables": {"json": json_path}}},
        "metrics_update": {"missing_credentials": len(missing)},
        "notes": notes,
    }


def handle_thalos_alerts(activity: AgentActivity) -> Dict[str, Any]:
    """THALOS task_assigned: ciclo REAL de monitorizacion (thalos_v1).

    Antes devolvia "Monitor de alertas activo y validado" con acciones que no ejecutaba
    ("Simulacion de evento critico"...). Ahora delega en handle_thalos_v1_monitor.
    """
    if not _require_superuser(activity):
        return _blocked_superuser_required(activity.action_type or "task_assigned")
    from .thalos_v1 import handle_thalos_v1_monitor

    return handle_thalos_v1_monitor(activity)


def handle_thalos_backup(activity: AgentActivity) -> Dict[str, Any]:
    if not _require_superuser(activity):
        return _blocked_superuser_required(activity.action_type or "backup_created")

    # Fase 2 / Step 1: copia REAL (pg_dump) a almacenamiento externo; antes se copiaba
    # zeus.db del repo a disco efimero y se daba por buena.
    from services import thalos_backup_service

    payload = thalos_backup_service.create_backup(activity_id=activity.id)
    backup_created = bool(payload.get("backup_created"))

    prefix = f"{activity.id}_{activity.action_type}"
    json_path = utils.write_json("THALOS", prefix, payload, company_id=activity.company_id)
    utils.write_log("THALOS", prefix, payload)

    status = "completed" if backup_created else "failed"
    notes = payload.get("notes") or ("Copia creada." if backup_created else "Copia no creada.")

    return {
        "status": status,
        "details_update": {"automation": {"deliverables": {"json": json_path}}},
        "metrics_update": {"backup_created": 1 if backup_created else 0},
        "notes": notes,
    }

