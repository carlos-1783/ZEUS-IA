"""
JUSTICIA control layer v1 — execution_mode + audit metadata overlay.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

ExecutionMode = Literal["SIMULATED", "READ_ONLY", "REAL"]
DataOrigin = Literal["backend", "user_input", "mock", "mixed", "llm"]

MODULE_UI_BADGE: Dict[str, str] = {
    "system_audit": "REAL",
    "gdpr_audit": "SIMULADO",
    "contract_generator": "SIMULADO",
    "pdf_signer": "SIMULADO",
    "workspace": "SIMULADO",
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
        "JUSTICE_REAL_AUDIT_ENABLED": bool(getattr(settings, "JUSTICE_REAL_AUDIT_ENABLED", False)),
        "JUSTICE_READ_ONLY_MODE": bool(getattr(settings, "JUSTICE_READ_ONLY_MODE", True)),
    }


def resolve_execution_mode(module: str) -> ExecutionMode:
    flags = current_flags()
    if module == "system_audit" and flags["JUSTICE_REAL_AUDIT_ENABLED"]:
        return "REAL"
    if flags["JUSTICE_READ_ONLY_MODE"]:
        return "READ_ONLY"
    return "SIMULATED"


def wrap_response(
    body: Dict[str, Any],
    module: str,
    *,
    data_origin: DataOrigin,
    real_execution: Optional[bool] = None,
    ui_badge: Optional[str] = None,
    audit_trace: Optional[list] = None,
) -> Dict[str, Any]:
    mode = resolve_execution_mode(module)
    if real_execution is None:
        real_execution = mode == "REAL" or (mode == "READ_ONLY" and module == "system_audit")
    meta = ControlMetadata(
        execution_mode=mode,
        data_origin=data_origin,
        real_execution=real_execution,
        module=module,
        ui_badge=ui_badge or MODULE_UI_BADGE.get(module, "SIMULADO"),
        flags=current_flags(),
    )
    out: Dict[str, Any] = {
        **body,
        "execution_mode": meta.execution_mode,
        "data_origin": meta.data_origin,
        "real_execution": meta.real_execution,
        "justicia_control": meta.to_dict(),
    }
    if audit_trace is not None:
        out["audit_trace"] = audit_trace
    return out


def global_status_payload() -> Dict[str, Any]:
    flags = current_flags()
    if flags["JUSTICE_REAL_AUDIT_ENABLED"]:
        default_mode: ExecutionMode = "REAL"
    elif flags["JUSTICE_READ_ONLY_MODE"]:
        default_mode = "READ_ONLY"
    else:
        default_mode = "SIMULATED"

    return wrap_response(
        {
            "system_default_mode": default_mode,
            **flags,
            "module_badges": MODULE_UI_BADGE,
            "audit_api": "/api/v1/justicia/v1/system-audit",
            "core_principle": "nada sin trazabilidad a BD se considera ejecución válida",
        },
        "status",
        data_origin="backend",
        real_execution=flags["JUSTICE_REAL_AUDIT_ENABLED"],
    )
