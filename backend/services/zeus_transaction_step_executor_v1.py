"""Execute individual ZEUS transaction steps."""

from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from services.afrodita_ops_service_v1 import create_inventory_movement, create_ops_route
from services.afrodita_workspace_service_v1 import create_company_employee, execute_qr_checkin
from services.workspace_playbook_service_v1 import create_playbook
from services.zeus_data_pipeline_v1 import attach_pipeline_metadata
from services.zeus_transaction_context_v1 import workspace_writes_allowed

STEP_TIMEOUT_MS = 5000
MAX_RETRIES = 3


def execute_step(
    db: Session,
    user: User,
    *,
    module: str,
    action: str,
    step_input: Dict[str, Any],
    transaction_id: str,
) -> Dict[str, Any]:
    mod = module.upper()
    act = action.strip().lower()
    started = time.monotonic()

    if mod == "WORKSPACE":
        if not workspace_writes_allowed():
            raise HTTPException(
                status_code=409,
                detail="WORKSPACE writes blocked until transaction commit phase",
            )
        return _exec_workspace(db, user, act, step_input, transaction_id)

    if mod == "RRHH":
        out = _exec_rrhh(db, user, act, step_input)
    elif mod == "OPS":
        out = _exec_ops(db, user, act, step_input)
    else:
        raise HTTPException(status_code=422, detail=f"Unknown module: {module}")

    elapsed_ms = int((time.monotonic() - started) * 1000)
    if elapsed_ms > STEP_TIMEOUT_MS:
        raise HTTPException(status_code=504, detail=f"Step timeout ({elapsed_ms}ms)")
    return {**out, "transaction_id": transaction_id}


def execute_step_with_retry(
    db: Session,
    user: User,
    *,
    module: str,
    action: str,
    step_input: Dict[str, Any],
    transaction_id: str,
    max_retries: int = MAX_RETRIES,
) -> Dict[str, Any]:
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return execute_step(
                db,
                user,
                module=module,
                action=action,
                step_input=step_input,
                transaction_id=transaction_id,
            )
        except Exception as exc:
            last_err = exc
            if attempt < max_retries:
                time.sleep(0.05 * (2**attempt))
                continue
            raise last_err
    raise RuntimeError("unreachable")


def _exec_rrhh(db: Session, user: User, action: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    if action == "qr_check_in":
        code = (inp.get("qr_code") or "").strip()
        if not code:
            raise HTTPException(status_code=422, detail="qr_code required")
        result = execute_qr_checkin(db, user, code)
        return {"checkin_id": result.get("checkin_id"), "result": result}
    if action == "create_employee":
        body = create_company_employee(
            db,
            user,
            full_name=inp["full_name"],
            employee_code=inp["employee_code"],
            role_title=inp.get("role_title"),
            phone=inp.get("phone"),
            hourly_rate=float(inp.get("hourly_rate") or 0),
        )
        emp = body["employee"]
        return {"employee_id": emp["id"], "employee": emp, **body}
    raise HTTPException(status_code=422, detail=f"Unknown RRHH action: {action}")


def _exec_ops(db: Session, user: User, action: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    if action == "create_movement":
        return create_inventory_movement(
            db,
            user,
            product_id=int(inp["product_id"]),
            movement_type=inp.get("movement_type", "adjustment"),
            quantity=float(inp["quantity"]),
            reference=inp.get("reference"),
            notes=inp.get("notes"),
        )
    if action == "create_route":
        return create_ops_route(
            db,
            user,
            origin=inp["origin"],
            destination=inp["destination"],
            deliveries=inp.get("deliveries") or [],
        )
    raise HTTPException(status_code=422, detail=f"Unknown OPS action: {action}")


def _exec_workspace(
    db: Session,
    user: User,
    action: str,
    inp: Dict[str, Any],
    transaction_id: str,
) -> Dict[str, Any]:
    if action == "persist_playbook":
        payload = attach_pipeline_metadata(
            inp.get("agent_source", "afrodita"),
            {
                **(inp.get("content") or {}),
                "transaction_id": transaction_id,
            },
        )
        row = create_playbook(
            db,
            user,
            title=inp.get("title") or "ZEUS transaction playbook",
            content=payload,
            agent_source=inp.get("agent_source", "afrodita"),
        )
        return {"playbook_id": row.id, "title": row.title}
    if action == "persist_summary":
        return {"summary": inp, "transaction_id": transaction_id}
    raise HTTPException(status_code=422, detail=f"Unknown WORKSPACE action: {action}")
