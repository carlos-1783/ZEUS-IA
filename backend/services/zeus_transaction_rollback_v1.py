"""Compensation / rollback for ZEUS transaction steps."""

from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)


def compensate_step(
    db: Session,
    user: User,
    *,
    module: str,
    action: str,
    output: Dict[str, Any],
) -> Dict[str, Any]:
    mod = module.upper()
    act = action.strip().lower()
    try:
        if mod == "RRHH" and act == "qr_check_in":
            return _compensate_checkin(db, output)
        if mod == "RRHH" and act == "create_employee":
            return _compensate_employee(db, output)
        if mod == "OPS" and act == "create_movement":
            return _compensate_movement(db, user, output)
        if mod == "OPS" and act == "create_route":
            return _compensate_route(db, output)
        if mod == "WORKSPACE" and act in ("persist_playbook", "persist_summary"):
            return _compensate_playbook(db, output)
    except Exception as exc:
        logger.exception("[ZEUS_TX_ROLLBACK] compensation failed %s.%s", mod, act)
        return {"status": "FAILED", "error": str(exc)}
    return {"status": "SKIPPED", "reason": "no_compensation_defined"}


def _compensate_checkin(db: Session, output: Dict[str, Any]) -> Dict[str, Any]:
    from app.models.time_cost_checkin import TimeCostCheckin

    cid = output.get("checkin_id") or (output.get("result") or {}).get("checkin_id")
    if not cid:
        return {"status": "SKIPPED", "reason": "no_checkin_id"}
    row = db.query(TimeCostCheckin).filter(TimeCostCheckin.id == int(cid)).first()
    if row:
        db.delete(row)
        db.flush()
    return {"status": "DONE", "action": "delete_checkin", "checkin_id": cid}


def _compensate_employee(db: Session, output: Dict[str, Any]) -> Dict[str, Any]:
    from app.models.company_employee import CompanyEmployee

    emp = output.get("employee") or {}
    eid = output.get("employee_id") or emp.get("id")
    if not eid:
        return {"status": "SKIPPED", "reason": "no_employee_id"}
    row = db.query(CompanyEmployee).filter(CompanyEmployee.id == int(eid)).first()
    if row:
        db.delete(row)
        db.flush()
    return {"status": "DONE", "action": "delete_employee", "employee_id": eid}


def _compensate_movement(db: Session, user: User, output: Dict[str, Any]) -> Dict[str, Any]:
    from app.models.erp import InventoryMovement, Product
    from services.afrodita_ops_service_v1 import _sync_tpv_stock_for_product

    mov = output.get("movement") or {}
    mid = mov.get("id")
    if not mid:
        return {"status": "SKIPPED", "reason": "no_movement_id"}
    row = db.query(InventoryMovement).filter(InventoryMovement.id == int(mid)).first()
    if not row:
        return {"status": "DONE", "action": "movement_already_absent"}
    product = db.query(Product).filter(Product.id == row.product_id).first()
    if product:
        product.quantity_on_hand = float(product.quantity_on_hand or 0) - float(row.quantity or 0)
        _sync_tpv_stock_for_product(db, user, product, -float(row.quantity or 0))
    db.delete(row)
    db.flush()
    return {"status": "DONE", "action": "reverse_movement", "movement_id": mid}


def _compensate_route(db: Session, output: Dict[str, Any]) -> Dict[str, Any]:
    from app.models.ops_route import OpsRoute

    route = output.get("route") or {}
    rid = route.get("id")
    if not rid:
        return {"status": "SKIPPED", "reason": "no_route_id"}
    row = db.query(OpsRoute).filter(OpsRoute.id == int(rid)).first()
    if row:
        db.delete(row)
        db.flush()
    return {"status": "DONE", "action": "delete_route", "route_id": rid}


def _compensate_playbook(db: Session, output: Dict[str, Any]) -> Dict[str, Any]:
    from app.models.workspace_playbook import WorkspacePlaybook

    pid = output.get("playbook_id")
    if not pid:
        return {"status": "SKIPPED", "reason": "no_playbook_id"}
    row = db.query(WorkspacePlaybook).filter(WorkspacePlaybook.id == int(pid)).first()
    if row:
        db.delete(row)
        db.flush()
    return {"status": "DONE", "action": "delete_playbook", "playbook_id": pid}
