"""
ZEUS transaction system v1 — central orchestrator with validation, locks, rollback.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.zeus_transaction import ZeusTransaction
from services.zeus_execution_controller_v1 import assert_execution_writes, get_execution_status
from services.zeus_transaction_context_v1 import TransactionContext, reset_transaction_context, set_transaction_context
from services.zeus_transaction_events_v1 import append_event, emit_event
from services.zeus_transaction_lock_manager_v1 import LockAcquisitionError, acquire_locks, derive_lock_resources, release_locks
from services.zeus_transaction_rollback_v1 import compensate_step
from services.zeus_transaction_step_executor_v1 import execute_step_with_retry
from services.zeus_transaction_validation_v1 import validate_transaction
from services.workspace_playbook_service_v1 import create_playbook
from services.zeus_data_pipeline_v1 import attach_pipeline_metadata

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset({"COMMITTED", "ROLLED_BACK", "FAILED"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json_dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _json_load(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _normalize_step(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "step_id": raw.get("step_id") or str(uuid.uuid4()),
        "module": (raw.get("module") or "").upper(),
        "action": raw.get("action") or "",
        "status": "PENDING",
        "read_set": raw.get("read_set") or [],
        "write_set": raw.get("write_set") or [],
        "input": raw.get("input") or {},
        "output": {},
        "retry_count": 0,
        "max_retries": int(raw.get("max_retries") or 3),
        "compensation": {
            "enabled": True,
            "action": f"compensate_{raw.get('action', '')}",
            "status": "PENDING",
        },
        "started_at": None,
        "finished_at": None,
    }


def _serialize_row(row: ZeusTransaction) -> Dict[str, Any]:
    return {
        "transaction_id": row.transaction_id,
        "status": row.status,
        "execution_mode_at_start": row.execution_mode_at_start,
        "initiator": _json_load(row.initiator_json, {}),
        "context": _json_load(row.context_json, {}),
        "modules_involved": _json_load(row.modules_involved_json, []),
        "steps": _json_load(row.steps_json, []),
        "locks": _json_load(row.locks_json, []),
        "validation": _json_load(row.validation_json, {}),
        "result": _json_load(row.result_json, {}),
        "errors": _json_load(row.errors_json, []),
        "metrics": _json_load(row.metrics_json, {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _load_row(db: Session, transaction_id: str) -> ZeusTransaction:
    row = (
        db.query(ZeusTransaction)
        .filter(ZeusTransaction.transaction_id == transaction_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")
    return row


def create_transaction(
    db: Session,
    user: User,
    *,
    initiator: Dict[str, Any],
    context: Dict[str, Any],
    steps: List[Dict[str, Any]],
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    if idempotency_key:
        existing = (
            db.query(ZeusTransaction)
            .filter(ZeusTransaction.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return _serialize_row(existing)

    execution = get_execution_status(db)
    mode = execution["execution_mode"]
    if mode == "SIMULATED":
        exec_at_start = "REAL_DEGRADED"
    else:
        exec_at_start = mode

    normalized = [_normalize_step(s) for s in steps]
    if not normalized:
        raise HTTPException(status_code=422, detail="At least one step required")

    modules = sorted({s["module"] for s in normalized if s["module"]})
    tx_id = str(uuid.uuid4())
    ctx = {
        **(context or {}),
        "user_id": str(user.id),
        "correlation_id": context.get("correlation_id") or tx_id,
        "request_id": context.get("request_id") or str(uuid.uuid4()),
    }

    metrics: Dict[str, Any] = {"events": [], "step_count": len(normalized)}
    append_event(metrics, emit_event("TRANSACTION_CREATED", transaction_id=tx_id))

    row = ZeusTransaction(
        transaction_id=tx_id,
        status="PENDING",
        execution_mode_at_start=exec_at_start,
        initiator_json=_json_dump(initiator),
        context_json=_json_dump(ctx),
        modules_involved_json=_json_dump(modules),
        steps_json=_json_dump(normalized),
        locks_json=_json_dump([]),
        validation_json=_json_dump({}),
        result_json=_json_dump({}),
        errors_json=_json_dump([]),
        metrics_json=_json_dump(metrics),
        idempotency_key=idempotency_key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_row(row)


def get_transaction(db: Session, transaction_id: str) -> Dict[str, Any]:
    return _serialize_row(_load_row(db, transaction_id))


def execute_transaction(db: Session, user: User, transaction_id: str) -> Dict[str, Any]:
    row = _load_row(db, transaction_id)
    if row.status in TERMINAL_STATUSES:
        return _serialize_row(row)
    if row.status == "IN_PROGRESS":
        raise HTTPException(status_code=409, detail="Transaction already IN_PROGRESS")

    steps: List[Dict[str, Any]] = _json_load(row.steps_json, [])
    metrics: Dict[str, Any] = _json_load(row.metrics_json, {})
    errors: List[Dict[str, Any]] = _json_load(row.errors_json, [])
    locks: List[Dict[str, Any]] = []
    started = time.monotonic()
    token = set_transaction_context(TransactionContext(transaction_id=transaction_id, phase="EXECUTING"))

    try:
        validation = validate_transaction(db, user, steps=steps)
        row.validation_json = _json_dump(validation)
        if not validation["passed"]:
            row.status = "FAILED"
            errors.append({"phase": "validation", "errors": validation["errors"]})
            row.errors_json = _json_dump(errors)
            append_event(metrics, emit_event("STEP_FAILED", transaction_id=transaction_id, payload=validation))
            row.metrics_json = _json_dump(metrics)
            row.updated_at = _now()
            db.commit()
            return _serialize_row(row)

        assert_execution_writes(db)

        row.status = "IN_PROGRESS"
        row.updated_at = _now()
        append_event(metrics, emit_event("TRANSACTION_STARTED", transaction_id=transaction_id))

        lock_specs = derive_lock_resources(steps, user.id)
        try:
            locks = acquire_locks(transaction_id, lock_specs)
            row.locks_json = _json_dump(locks)
        except LockAcquisitionError as exc:
            row.status = "FAILED"
            errors.append({"phase": "locks", "error": str(exc)})
            row.errors_json = _json_dump(errors)
            row.metrics_json = _json_dump(metrics)
            db.commit()
            return _serialize_row(row)

        completed: List[Dict[str, Any]] = []
        deferred_workspace: List[Dict[str, Any]] = []

        for step in steps:
            if step["module"] == "WORKSPACE":
                deferred_workspace.append(step)
                step["status"] = "SKIPPED"
                step["finished_at"] = _now().isoformat()
                continue

            step["status"] = "RUNNING"
            step["started_at"] = _now().isoformat()
            append_event(
                metrics,
                emit_event(
                    "STEP_STARTED",
                    transaction_id=transaction_id,
                    payload={"step_id": step["step_id"], "module": step["module"]},
                ),
            )

            savepoint = db.begin_nested()
            try:
                output = execute_step_with_retry(
                    db,
                    user,
                    module=step["module"],
                    action=step["action"],
                    step_input=step["input"],
                    transaction_id=transaction_id,
                    max_retries=step.get("max_retries", 3),
                )
                savepoint.commit()
                step["status"] = "SUCCESS"
                step["output"] = output
                step["finished_at"] = _now().isoformat()
                completed.append(step)
                append_event(
                    metrics,
                    emit_event(
                        "STEP_COMPLETED",
                        transaction_id=transaction_id,
                        payload={"step_id": step["step_id"]},
                    ),
                )
            except Exception as exc:
                savepoint.rollback()
                step["status"] = "FAILED"
                step["finished_at"] = _now().isoformat()
                errors.append(
                    {
                        "step_id": step["step_id"],
                        "module": step["module"],
                        "action": step["action"],
                        "error": str(exc),
                    }
                )
                append_event(
                    metrics,
                    emit_event(
                        "STEP_FAILED",
                        transaction_id=transaction_id,
                        payload={"step_id": step["step_id"], "error": str(exc)},
                    ),
                )
                _run_compensation(db, user, completed, steps)
                row.status = "ROLLED_BACK"
                row.steps_json = _json_dump(steps)
                row.errors_json = _json_dump(errors)
                append_event(metrics, emit_event("TRANSACTION_ROLLED_BACK", transaction_id=transaction_id))
                row.metrics_json = _json_dump(_finalize_metrics(metrics, started))
                row.updated_at = _now()
                release_locks(transaction_id, locks)
                row.locks_json = _json_dump(locks)
                db.commit()
                return _serialize_row(row)

        # Commit phase — WORKSPACE writes only here
        set_transaction_context(TransactionContext(transaction_id=transaction_id, phase="COMMITTING"))
        workspace_outputs: List[Dict[str, Any]] = []
        for step in deferred_workspace:
            step["status"] = "RUNNING"
            step["started_at"] = _now().isoformat()
            try:
                out = execute_step_with_retry(
                    db,
                    user,
                    module="WORKSPACE",
                    action=step["action"],
                    step_input=step["input"],
                    transaction_id=transaction_id,
                )
                step["status"] = "SUCCESS"
                step["output"] = out
                workspace_outputs.append(out)
            except Exception as exc:
                step["status"] = "FAILED"
                errors.append({"step_id": step["step_id"], "error": str(exc)})
                _run_compensation(db, user, completed, steps)
                row.status = "ROLLED_BACK"
                row.steps_json = _json_dump(steps)
                row.errors_json = _json_dump(errors)
                append_event(metrics, emit_event("TRANSACTION_ROLLED_BACK", transaction_id=transaction_id))
                row.metrics_json = _json_dump(_finalize_metrics(metrics, started))
                release_locks(transaction_id, locks)
                row.locks_json = _json_dump(locks)
                db.commit()
                return _serialize_row(row)
            step["finished_at"] = _now().isoformat()

        if not deferred_workspace:
            workspace_outputs.extend(_auto_workspace_playbooks(db, user, transaction_id, completed))

        row.status = "COMMITTED"
        row.result_json = _json_dump({"steps": completed, "workspace": workspace_outputs})
        row.steps_json = _json_dump(steps)
        append_event(metrics, emit_event("TRANSACTION_COMMITTED", transaction_id=transaction_id))
        row.metrics_json = _json_dump(_finalize_metrics(metrics, started))
        row.updated_at = _now()
        release_locks(transaction_id, locks)
        row.locks_json = _json_dump(locks)
        db.commit()
        db.refresh(row)
        return _serialize_row(row)
    finally:
        reset_transaction_context(token)


def _run_compensation(
    db: Session,
    user: User,
    completed: List[Dict[str, Any]],
    all_steps: List[Dict[str, Any]],
) -> None:
    for step in reversed(completed):
        comp = step.get("compensation") or {}
        try:
            result = compensate_step(
                db,
                user,
                module=step["module"],
                action=step["action"],
                output=step.get("output") or {},
            )
            comp["status"] = result.get("status", "DONE")
            comp["result"] = result
        except Exception as exc:
            comp["status"] = "FAILED"
            comp["result"] = {"error": str(exc)}
        step["compensation"] = comp
    for step in all_steps:
        if step.get("status") == "SKIPPED":
            step["status"] = "SKIPPED"


def _auto_workspace_playbooks(
    db: Session,
    user: User,
    transaction_id: str,
    completed: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Persist orchestration summary playbooks after successful RRHH/OPS steps."""
    outputs: List[Dict[str, Any]] = []
    for step in completed:
        mod = step["module"].lower()
        if mod not in ("rrhh", "ops"):
            continue
        agent_source = "logistics" if step["action"] == "create_route" else mod
        payload = attach_pipeline_metadata(
            agent_source,
            {
                "action": step["action"],
                "transaction_id": transaction_id,
                "result": step.get("output"),
                "execution": "REAL",
            },
        )
        row = create_playbook(
            db,
            user,
            title=f"TX {transaction_id[:8]} — {step['action']}",
            content=payload,
            agent_source=agent_source,
        )
        outputs.append({"playbook_id": row.id, "step_id": step["step_id"]})
    return outputs


def _finalize_metrics(metrics: Dict[str, Any], started: float) -> Dict[str, Any]:
    metrics["duration_ms"] = int((time.monotonic() - started) * 1000)
    return metrics


def get_health(db: Session) -> Dict[str, Any]:
    active = db.query(ZeusTransaction).filter(ZeusTransaction.status == "IN_PROGRESS").count()
    failed = (
        db.query(ZeusTransaction)
        .filter(ZeusTransaction.status.in_(["FAILED", "ROLLED_BACK"]))
        .count()
    )
    execution = get_execution_status(db)
    inconsistencies: List[str] = []
    if execution["flag_consistency"] != "UNIFIED":
        inconsistencies.append("flag_consistency_degraded")
    if execution["execution_mode"] == "ERROR":
        inconsistencies.append("database_error")
    system_status = "OK"
    if inconsistencies:
        system_status = "DEGRADED"
    if execution["execution_mode"] == "ERROR":
        system_status = "ERROR"
    return {
        "system_status": system_status,
        "active_transactions": int(active) if isinstance(active, int) else 0,
        "failed_transactions": int(failed) if isinstance(failed, int) else 0,
        "inconsistencies": inconsistencies,
        "execution_mode": execution["execution_mode"],
        "writes_enabled": execution["writes_enabled"],
    }
