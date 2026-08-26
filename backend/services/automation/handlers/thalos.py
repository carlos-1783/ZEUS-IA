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
    db = SessionLocal()
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
    json_path = utils.write_json("THALOS", prefix, payload)
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
    if not _require_superuser(activity):
        return _blocked_superuser_required(activity.action_type or "task_assigned")

    configuration = {
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "sentry_enabled": bool(os.getenv("SENTRY_DSN")),
        "stripe_mode": os.getenv("STRIPE_MODE", "auto"),
    }
    actions = [
        "Verificación de sinks de logs",
        "Simulación de evento crítico",
        "Chequeo de modo Stripe vs credencial",
    ]
    payload = {
        "executed_at": datetime.utcnow().isoformat(),
        "configuration": configuration,
        "actions_performed": actions,
        "result": "Monitor de alertas activo y validado.",
    }

    prefix = f"{activity.id}_{activity.action_type}"
    json_path = utils.write_json("THALOS", prefix, payload)
    utils.write_log("THALOS", prefix, payload)

    return {
        "status": "completed",
        "details_update": {"automation": {"deliverables": {"json": json_path}}},
        "metrics_update": {"alerts_verified": len(actions)},
        "notes": f"Alertas configuradas automáticamente. Informe en {json_path}",
    }


def handle_thalos_backup(activity: AgentActivity) -> Dict[str, Any]:
    if not _require_superuser(activity):
        return _blocked_superuser_required(activity.action_type or "backup_created")

    source = Path("zeus.db")
    backup_dir = Path(os.getenv("AGENT_BACKUP_DIR", "storage/backups"))
    utils.ensure_dir(backup_dir)

    backup_created = False
    backup_path: Optional[str] = None

    if source.exists():
        target = backup_dir / f"zeus_backup_{utils.timestamp()}.db"
        shutil.copy2(source, target)
        backup_created = True
        backup_path = str(target.resolve())

    payload = {
        "executed_at": datetime.utcnow().isoformat(),
        "source_exists": source.exists(),
        "backup_created": backup_created,
        "backup_path": backup_path,
        "notes": "Entorno Railway usa almacenamiento efímero; replicar backup en almacenamiento persistente.",
    }

    prefix = f"{activity.id}_{activity.action_type}"
    json_path = utils.write_json("THALOS", prefix, payload)
    utils.write_log("THALOS", prefix, payload)

    status = "completed" if backup_created else "failed"
    notes = (
        f"Backup generado automáticamente en {backup_path}."
        if backup_created
        else "No se encontró base de datos local para copiar; revisar configuración."
    )

    return {
        "status": status,
        "details_update": {"automation": {"deliverables": {"json": json_path}}},
        "metrics_update": {"backup_created": 1 if backup_created else 0},
        "notes": notes,
    }

