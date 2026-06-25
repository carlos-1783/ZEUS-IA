"""Compatibility shim — delegates to services.afrodita_unified_control."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from services import afrodita_unified_control as _u

ExecutionMode = _u.ExecutionMode
DataOrigin = _u.DataOrigin
MODULE_UI_BADGE: Dict[str, str] = {}

current_flags = _u.current_flags
writes_enabled = _u.writes_enabled
can_write_stock = _u.can_write_stock
route_engine_available = _u.route_engine_available
global_status_payload = _u.get_global_status
wrap_response = _u.wrap_response


def log_ops_attempt(
    *,
    module: str,
    action: Optional[str],
    allowed: bool,
    actor_id: Optional[int] = None,
) -> None:
    _u.log_execution_attempt(domain=module, action=action, allowed=allowed, actor_id=actor_id)
