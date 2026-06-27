"""
THALOS control layer v1 — separa SIMULATION / REAL_SAFE / REAL_ACTIVE en metadata.

Non-destructive overlay: no cambia lógica de negocio; envuelve respuestas API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from app.core.config import settings
from services.execution_mode_v1 import normalize_execution_mode

logger = logging.getLogger(__name__)

ExecutionMode = Literal["SIMULATION", "REAL_SAFE", "REAL_ACTIVE"]
DataOrigin = Literal["backend", "user_input", "mock", "mixed"]
ModuleId = Literal[
    "auditoria_real",
    "backup_system",
    "log_monitor",
    "text_analysis",
    "workspace",
    "events",
    "status",
]

MODULE_CLASSIFICATION: Dict[str, str] = {
    "auditoria_real": "REAL_SAFE",
    "backup_system": "REAL_CONDITIONAL",
    "log_monitor": "REAL_SAFE",
    "text_analysis": "REAL_SAFE",
    "workspace": "REAL_SAFE",
    "events": "REAL_SAFE",
    "status": "REAL_SAFE",
}

MODULE_UI_BADGE: Dict[str, str] = {
    "auditoria_real": "REAL",
    "backup_system": "REAL",
    "log_monitor": "REAL",
    "text_analysis": "REAL",
    "workspace": "REAL",
    "events": "REAL",
    "status": "REAL",
}


@dataclass
class ControlMetadata:
    execution_mode: ExecutionMode
    data_origin: DataOrigin
    real_execution: bool
    module: str
    ui_badge: str
    flags: Dict[str, bool]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_mode": self.execution_mode,
            "data_origin": self.data_origin,
            "real_execution": self.real_execution,
            "module": self.module,
            "ui_badge": self.ui_badge,
            "flags": self.flags,
        }


def current_flags() -> Dict[str, bool]:
    return {
        "THALOS_EXECUTION_ENABLED": bool(settings.THALOS_EXECUTION_ENABLED),
        "THALOS_REAL_LOGS_ENABLED": bool(getattr(settings, "THALOS_REAL_LOGS_ENABLED", False)),
        "THALOS_BACKUP_ENABLED": bool(getattr(settings, "THALOS_BACKUP_ENABLED", False)),
        "THALOS_REAL_MONITORING": bool(settings.THALOS_REAL_MONITORING),
        "THALOS_WORKSPACE_WRITE_ENABLED": bool(settings.THALOS_WORKSPACE_WRITE_ENABLED),
    }


def resolve_execution_mode(module: str) -> ExecutionMode:
    """Modo efectivo según módulo + flags globales."""
    if not getattr(settings, "THALOS_ENABLED", True):
        return "SIMULATION"

    mod = (module or "").strip().lower()
    classification = MODULE_CLASSIFICATION.get(mod, "REAL_SAFE")

    if classification == "SIMULATION":
        return "SIMULATION"

    if mod == "backup_system":
        if settings.THALOS_EXECUTION_ENABLED and getattr(settings, "THALOS_BACKUP_ENABLED", False):
            return "REAL_ACTIVE"
        if getattr(settings, "THALOS_BACKUP_ENABLED", False):
            return "REAL_SAFE"
        return "REAL_SAFE"

    if mod in ("log_monitor", "text_analysis") and (
        settings.THALOS_REAL_LOGS_ENABLED or settings.THALOS_REAL_MONITORING
    ):
        return "REAL_ACTIVE" if settings.THALOS_EXECUTION_ENABLED else "REAL_SAFE"

    if classification == "REAL_SAFE":
        return "REAL_SAFE"

    if classification == "REAL_CONDITIONAL":
        return "REAL_ACTIVE" if settings.THALOS_EXECUTION_ENABLED else "REAL_SAFE"

    return "REAL_SAFE"


def can_run_active_execution(module: str, action: Optional[str] = None) -> bool:
    """Bloquea ejecución destructiva si mode != REAL_ACTIVE."""
    mode = resolve_execution_mode(module)
    if mode == "REAL_ACTIVE":
        return True
    if mode == "REAL_SAFE" and action in (
        "detect_suspicious_activity",
        "security_monitor",
        "audit_cashflow_anomaly",
        None,
    ):
        return True
    return False


def log_execution_attempt(
    *,
    module: str,
    action: Optional[str],
    allowed: bool,
    actor_id: Optional[int] = None,
) -> None:
    logger.info(
        "[THALOS_CONTROL] module=%s action=%s mode=%s allowed=%s actor=%s",
        module,
        action,
        resolve_execution_mode(module),
        allowed,
        actor_id,
    )


def build_metadata(
    module: str,
    *,
    data_origin: DataOrigin,
    real_execution: Optional[bool] = None,
) -> ControlMetadata:
    mode = resolve_execution_mode(module)
    if real_execution is None:
        real_execution = mode in ("REAL_SAFE", "REAL_ACTIVE")
    return ControlMetadata(
        execution_mode=mode,
        data_origin=data_origin,
        real_execution=real_execution,
        module=module,
        ui_badge=MODULE_UI_BADGE.get(module, "SIMULADO"),
        flags=current_flags(),
    )


def wrap_response(
    body: Dict[str, Any],
    module: str,
    *,
    data_origin: DataOrigin,
    real_execution: Optional[bool] = None,
) -> Dict[str, Any]:
    """Añade contrato thalos_control a cada respuesta."""
    meta = build_metadata(module, data_origin=data_origin, real_execution=real_execution)
    return {
        **body,
        "execution_mode": meta.execution_mode,
        "standard_execution_mode": normalize_execution_mode(meta.execution_mode),
        "data_origin": meta.data_origin,
        "real_execution": meta.real_execution,
        "thalos_control": meta.to_dict(),
    }


def global_status_payload() -> Dict[str, Any]:
    """Estado global para badge UI — derived from DB counts when possible."""
    default_mode: ExecutionMode = "REAL_SAFE"
    if settings.THALOS_EXECUTION_ENABLED:
        default_mode = "REAL_ACTIVE"
    elif settings.THALOS_REAL_MONITORING or settings.THALOS_REAL_LOGS_ENABLED:
        default_mode = "REAL_ACTIVE" if settings.THALOS_EXECUTION_ENABLED else "REAL_SAFE"

    db_stats: Dict[str, Any] = {}
    try:
        from app.db.session import SessionLocal
        from services.thalos_monitor_service import audit_from_db

        db = SessionLocal()
        try:
            db_stats = audit_from_db(db)
        finally:
            db.close()
    except Exception:
        db_stats = {}

    from workers.thalos_worker import worker_status

    return wrap_response(
        {
            "system_default_mode": default_mode,
            "thalos_enabled": bool(getattr(settings, "THALOS_ENABLED", True)),
            "worker": worker_status(),
            "database": db_stats,
            **current_flags(),
            "module_classification": MODULE_CLASSIFICATION,
            "strict_real_mode": True,
        },
        "status",
        data_origin="backend",
        real_execution=bool(getattr(settings, "THALOS_ENABLED", True)),
    )
