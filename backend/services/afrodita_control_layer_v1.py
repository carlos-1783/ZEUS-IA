"""Compatibility shim — delegates to services.afrodita_unified_control."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from services import afrodita_unified_control as _u

ExecutionMode = _u.ExecutionMode
DataOrigin = _u.DataOrigin
DAY_NAMES = _u.DAY_NAMES
MODULE_UI_BADGE: Dict[str, str] = {}

current_flags = _u.current_flags
writes_enabled = _u.writes_enabled
probe_db_connected = _u.probe_db_connected
resolve_execution_mode = _u.resolve_execution_mode
get_global_status = _u.get_global_status
assert_can_write = _u.assert_can_write
can_create_employee = _u.can_create_employee
can_execute_checkin = _u.can_execute_checkin
can_write_stock = _u.can_write_stock
wrap_response = _u.wrap_response
parse_zeuscheck_code = _u.parse_zeuscheck_code
validate_qr_freshness = _u.validate_qr_freshness

afrodita_truth_status_payload = _u.get_global_status
global_status_payload = _u.get_global_status


def log_execution_attempt(
    *,
    module: str,
    action: Optional[str],
    allowed: bool,
    actor_id: Optional[int] = None,
) -> None:
    _u.log_execution_attempt(domain=module, action=action, allowed=allowed, actor_id=actor_id)
