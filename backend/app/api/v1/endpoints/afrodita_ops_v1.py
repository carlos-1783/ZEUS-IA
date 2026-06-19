"""AFRODITA OPS v1 API — inventario unificado, movimientos, rutas simuladas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.afrodita_ops_control_layer_v1 import global_status_payload, log_ops_attempt, wrap_response
from services.afrodita_ops_service_v1 import (
    list_inventory_movements,
    merge_products_view,
    simulate_route,
)

router = APIRouter(prefix="/afrodita/ops/v1", tags=["afrodita-ops-v1"])


class RouteSimulateRequest(BaseModel):
    deliveries: List[Dict[str, Any]] = Field(default_factory=list)
    start_location: str = "depot"


@router.get("/status")
def afrodita_ops_status(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return global_status_payload()


@router.get("/inventory")
def afrodita_ops_inventory(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    log_ops_attempt(
        module="inventory_core",
        action="merged_inventory",
        allowed=True,
        actor_id=current_user.id,
    )
    body = merge_products_view(db, current_user)
    return wrap_response(
        {"success": True, **body},
        "inventory_core",
        data_origin="backend",
        real_execution=True,
        ui_badge="REAL",
    )


@router.get("/movements")
def afrodita_ops_movements(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    log_ops_attempt(
        module="goods_layer",
        action="list_movements",
        allowed=True,
        actor_id=current_user.id,
    )
    body = list_inventory_movements(db, limit=limit)
    real = bool(body.get("movements"))
    return wrap_response(
        {"success": True, **body},
        "goods_layer",
        data_origin="backend",
        real_execution=real,
        ui_badge="PARTIAL" if real else "SIMULADO",
    )


@router.post("/routes/simulate")
def afrodita_ops_route_simulate(
    body: RouteSimulateRequest,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    log_ops_attempt(
        module="route_planner",
        action="simulate_route",
        allowed=True,
        actor_id=current_user.id,
    )
    result = simulate_route(body.deliveries, body.start_location)
    return wrap_response(
        {"success": True, "result": result},
        "route_planner",
        data_origin="mock",
        real_execution=False,
        ui_badge="SIMULADO",
    )


@router.get("/warehouse")
def afrodita_ops_warehouse_stub(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return wrap_response(
        {
            "success": True,
            "implemented": False,
            "label": "No implementado",
            "note": "Almacén (bins/ubicaciones) — fase 3 ops_build",
        },
        "warehouse_management",
        data_origin="mock",
        real_execution=False,
        ui_badge="NONE",
    )
