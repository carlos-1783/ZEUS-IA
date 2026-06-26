"""ZEUS transaction event log (observability)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("zeus.transaction.events")

EVENT_TYPES = (
    "TRANSACTION_CREATED",
    "TRANSACTION_STARTED",
    "STEP_STARTED",
    "STEP_COMPLETED",
    "STEP_FAILED",
    "TRANSACTION_COMMITTED",
    "TRANSACTION_ROLLED_BACK",
)


def emit_event(event_type: str, *, transaction_id: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    body = {
        "event": event_type,
        "transaction_id": transaction_id,
        "trace_id": transaction_id,
        **(payload or {}),
    }
    logger.info("[ZEUS_TX_EVENT] %s tx=%s payload=%s", event_type, transaction_id, payload)
    return body


def append_event(metrics: Dict[str, Any], event: Dict[str, Any]) -> None:
    events: List[Dict[str, Any]] = metrics.setdefault("events", [])
    events.append(event)
