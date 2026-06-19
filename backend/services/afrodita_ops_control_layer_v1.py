"""
AFRODITA OPS control layer v1 — inventario TPV + ERP, badges REAL/SIMULADO/NONE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

ExecutionMode = Literal["SIMULATION", "READ_ONLY", "REAL_ACTIVE"]
DataOrigin = Literal["backend", "user_input", "mock", "mixed"]

MODULE_UI_BADGE: Dict[str, str] = {
    "inventory_core": "REAL",
    "goods_layer": "PARTIAL",
    "warehouse_management": "NONE",
    "route_planner": "SIMULADO",
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
        "AFRODITA_OPS_ENABLED": bool(getattr(settings, "AFRODITA_OPS_ENABLED", False)),
        "AFRODITA_OPS_READ_ONLY": bool(getattr(settings, "AFRODITA_OPS_READ_ONLY", True)),
        "AFRODITA_USE_TPV": bool(getattr(settings, "AFRODITA_USE_TPV", True)),
        "AFRODITA_USE_ERP": bool(getattr(settings, "AFRODITA_USE_ERP", True)),
        "AFRODITA_ENABLE_STOCK_SYNC": bool(getattr(settings, "AFRODITA_ENABLE_STOCK_SYNC", False)),
        "AFRODITA_ENABLE_ROUTE_ENGINE": bool(getattr(settings, "AFRODITA_ENABLE_ROUTE_ENGINE", False)),
    }


def resolve_execution_mode(module: str) -> ExecutionMode:
    flags = current_flags()
    if flags["AFRODITA_OPS_ENABLED"] and not flags["AFRODITA_OPS_READ_ONLY"]:
        if module in ("inventory_core", "goods_layer"):
            return "REAL_ACTIVE"
    if flags["AFRODITA_OPS_READ_ONLY"]:
        return "READ_ONLY"
    return "SIMULATION"


def can_write_stock() -> bool:
    f = current_flags()
    return f["AFRODITA_OPS_ENABLED"] and not f["AFRODITA_OPS_READ_ONLY"] and f["AFRODITA_ENABLE_STOCK_SYNC"]


def log_ops_attempt(*, module: str, action: str, allowed: bool, actor_id: Optional[int] = None) -> None:
    logger.info(
        "[AFRODITA_OPS] module=%s action=%s mode=%s allowed=%s actor=%s",
        module,
        action,
        resolve_execution_mode(module),
        allowed,
        actor_id,
    )


def wrap_response(
    body: Dict[str, Any],
    module: str,
    *,
    data_origin: DataOrigin,
    real_execution: Optional[bool] = None,
    ui_badge: Optional[str] = None,
) -> Dict[str, Any]:
    mode = resolve_execution_mode(module)
    if real_execution is None:
        real_execution = mode in ("READ_ONLY", "REAL_ACTIVE") and module not in (
            "warehouse_management",
            "route_planner",
        )
    meta = ControlMetadata(
        execution_mode=mode,
        data_origin=data_origin,
        real_execution=real_execution,
        module=module,
        ui_badge=ui_badge or MODULE_UI_BADGE.get(module, "SIMULADO"),
        flags=current_flags(),
    )
    return {
        **body,
        "execution_mode": meta.execution_mode,
        "data_origin": meta.data_origin,
        "real_execution": meta.real_execution,
        "afrodita_ops_control": meta.to_dict(),
    }


def global_status_payload() -> Dict[str, Any]:
    flags = current_flags()
    if flags["AFRODITA_OPS_ENABLED"] and not flags["AFRODITA_OPS_READ_ONLY"]:
        default_mode: ExecutionMode = "REAL_ACTIVE"
    elif flags["AFRODITA_OPS_READ_ONLY"]:
        default_mode = "READ_ONLY"
    else:
        default_mode = "SIMULATION"

    return wrap_response(
        {
            "system_default_mode": default_mode,
            **flags,
            "module_badges": MODULE_UI_BADGE,
            "erp_api_path": "/api/v1/products",
            "tpv_api_path": "/api/v1/tpv/products",
            "inventory_precedence": "erp",
            "legacy_preserved": True,
        },
        "status",
        data_origin="backend",
        real_execution=True,
    )
