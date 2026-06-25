"""AFRODITA OPS v1 API — inventario y movimientos (modo unificado)."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.afrodita_ops_service_v1 import list_inventory_movements, merge_products_view
from services.afrodita_unified_control import (
    get_global_status,
    log_execution_attempt,
    route_engine_available,
    wrap_response,
)

router = APIRouter(prefix="/afrodita/ops/v1", tags=["afrodita-ops-v1"])


class RouteSimulateRequest(BaseModel):
    deliveries: List[Dict[str, Any]] = Field(default_factory=list)
    start_location: str = "depot"


@router.get("/status")
def afrodita_ops_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    return get_global_status(db)


@router.get("/inventory")
def afrodita_ops_inventory(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    log_execution_attempt(
        domain="inventory_core",
        action="merged_inventory",
        allowed=True,
        actor_id=current_user.id,
    )
    body = merge_products_view(db, current_user)
    return wrap_response(
        {"success": True, **body},
        db=db,
        data_origin="backend",
        read_only=True,
    )


@router.get("/movements")
def afrodita_ops_movements(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    log_execution_attempt(
        domain="goods_layer",
        action="list_movements",
        allowed=True,
        actor_id=current_user.id,
    )
    body = list_inventory_movements(db, limit=limit)
    return wrap_response(
        {"success": True, **body},
        db=db,
        data_origin="backend",
        read_only=True,
    )


@router.post("/routes/simulate")
def afrodita_ops_route_simulate(
    body: RouteSimulateRequest,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    _ = body, current_user
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "error": "route_engine_not_implemented",
            "execution_mode": get_global_status().get("execution_mode", "SIMULATED"),
            "route_engine_enabled": route_engine_available(),
            "message": "Motor de rutas no implementado — use AFRODITA_ENABLE_ROUTE_ENGINE cuando exista engine real",
            "success": False,
        },
    )


@router.get("/warehouse")
def afrodita_ops_warehouse_stub(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    return wrap_response(
        {
            "success": False,
            "implemented": False,
            "label": "No implementado",
            "note": "Almacén (bins/ubicaciones) — fase 3 ops_build",
        },
        db=db,
        data_origin="mock",
        dry_run=True,
        read_only=True,
    )
