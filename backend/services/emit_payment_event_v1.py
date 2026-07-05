"""Synthetic payment_due event payload for Phase C safe production test."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def build_payment_due_payload() -> Dict[str, Any]:
    """Demo pending payment — amount 1250 triggers high risk."""
    now = datetime.now(timezone.utc)
    return {
        "client_id": f"demo-client-{int(now.timestamp())}",
        "name": "Demo Client Phase C",
        "amount": 1250,
        "status": "pending",
        "phase_c": True,
        "due_at": now.isoformat(),
    }
