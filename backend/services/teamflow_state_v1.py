"""TeamFlow global state machine — valid states and transitions."""

from __future__ import annotations

from typing import Dict, FrozenSet, Set

VALID_STATUSES: FrozenSet[str] = frozenset(
    {"draft", "pending", "approved", "rejected", "in_progress", "completed"}
)

VALID_TRANSITIONS: Dict[str, Set[str]] = {
    "draft": {"pending", "in_progress", "rejected"},
    "pending": {"approved", "rejected", "in_progress"},
    "in_progress": {"completed", "pending", "rejected"},
    "approved": {"completed"},
    "rejected": {"draft"},
    "completed": set(),
}


def can_transition(from_status: str, to_status: str) -> bool:
    if to_status not in VALID_STATUSES:
        return False
    if from_status not in VALID_STATUSES:
        return False
    if from_status == to_status:
        return True
    return to_status in VALID_TRANSITIONS.get(from_status, set())
