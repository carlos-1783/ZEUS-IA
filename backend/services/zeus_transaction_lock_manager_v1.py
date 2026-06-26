"""In-process resource locks for ZEUS transactions."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

_lock = threading.RLock()
_active: Dict[str, Tuple[str, str]] = {}  # resource -> (transaction_id, lock_type)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def acquire_locks(transaction_id: str, resources: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    acquired: List[Dict[str, Any]] = []
    with _lock:
        for spec in resources:
            resource = spec["resource"]
            lock_type = spec.get("lock_type", "WRITE")
            holder = _active.get(resource)
            if holder and holder[0] != transaction_id:
                if holder[1] == "WRITE" or lock_type == "WRITE":
                    release_locks(transaction_id, acquired)
                    raise LockAcquisitionError(f"Resource locked: {resource} by {holder[0]}")
            _active[resource] = (transaction_id, lock_type)
            acquired.append(
                {
                    "resource": resource,
                    "lock_type": lock_type,
                    "status": "ACTIVE",
                    "acquired_at": _now(),
                    "released_at": None,
                }
            )
    return acquired


def release_locks(transaction_id: str, locks: Optional[List[Dict[str, Any]]] = None) -> None:
    with _lock:
        if locks:
            for entry in locks:
                resource = entry.get("resource")
                if resource and _active.get(resource, (None,))[0] == transaction_id:
                    del _active[resource]
                entry["status"] = "RELEASED"
                entry["released_at"] = _now()
        else:
            for resource, (tx_id, _) in list(_active.items()):
                if tx_id == transaction_id:
                    del _active[resource]


def derive_lock_resources(steps: List[Dict[str, Any]], user_id: int) -> List[Dict[str, str]]:
    resources: Set[str] = {f"user:{user_id}"}
    for step in steps:
        module = (step.get("module") or "").upper()
        action = step.get("action") or ""
        inp = step.get("input") or {}
        resources.add(f"module:{module}")
        if module == "OPS" and inp.get("product_id"):
            resources.add(f"product:{inp['product_id']}")
        if module == "RRHH" and inp.get("employee_code"):
            resources.add(f"employee_code:{inp['employee_code']}")
    return [{"resource": r, "lock_type": "WRITE"} for r in sorted(resources)]


class LockAcquisitionError(RuntimeError):
    pass
