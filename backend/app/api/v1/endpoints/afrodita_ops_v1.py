"""AFRODITA OPS v1 API — inventario, movimientos y rutas reales."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.afrodita_ops_service_v1 import (
    create_inventory_movement,
    create_ops_route,
    list_inventory_movements,
    list_ops_routes,
    merge_products_view,
    warehouse_summary,
)
from services.afrodita_unified_control import (
    assert_can_write,
    get_global_status,
    log_execution_attempt,
    wrap_response,
)

router = APIRouter(prefix="/afrodita/ops/v1", tags=["afrodita-ops-v1"])


class MovementCreateRequest(BaseModel):
    product_id: int = Field(..., gt=0)
    movement_type: str = Field(default="adjustment")
    quantity: float
    reference: Optional[str] = None
    notes: Optional[str] = None


class RouteCreateRequest(BaseModel):
    origin: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    deliveries: List[Dict[str, Any]] = Field(default_factory=list)


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
    _ = current_user
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


@router.post("/movements/create")
def afrodita_ops_movement_create(
    body: MovementCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    assert_can_write(db)
    log_execution_attempt(
        domain="goods_layer",
        action="create_movement",
        allowed=True,
        actor_id=current_user.id,
    )
    result = create_inventory_movement(
        db,
        current_user,
        product_id=body.product_id,
        movement_type=body.movement_type,
        quantity=body.quantity,
        reference=body.reference,
        notes=body.notes,
    )
    from services.workspace_playbook_writer_v1 import write_ops_playbook

    write_ops_playbook(
        db,
        current_user,
        action="create_movement",
        title=f"Movimiento #{result['movement']['id']}",
        payload=result,
    )
    db.commit()
    return wrap_response(
        {"success": True, **result},
        db=db,
        data_origin="backend",
        persisted=True,
    )


@router.get("/routes")
def afrodita_ops_routes_list(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = list_ops_routes(db, current_user, limit=limit)
    return wrap_response(
        {"success": True, **body},
        db=db,
        data_origin="backend",
        read_only=True,
    )


@router.post("/routes/create")
def afrodita_ops_route_create(
    body: RouteCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    assert_can_write(db)
    log_execution_attempt(
        domain="routes",
        action="create_route",
        allowed=True,
        actor_id=current_user.id,
    )
    result = create_ops_route(
        db,
        current_user,
        origin=body.origin,
        destination=body.destination,
        deliveries=body.deliveries,
    )
    from services.workspace_playbook_writer_v1 import write_logistics_playbook

    write_logistics_playbook(
        db,
        current_user,
        action="create_route",
        title=f"Ruta {body.origin} → {body.destination}",
        payload=result,
    )
    db.commit()
    return wrap_response(
        {"success": True, **result},
        db=db,
        data_origin="backend",
        persisted=True,
    )


@router.post("/routes/simulate")
def afrodita_ops_route_simulate_removed() -> None:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "error": "simulate_removed",
            "message": "Use POST /api/v1/afrodita/ops/v1/routes/create",
            "success": False,
        },
    )


@router.get("/warehouse")
def afrodita_ops_warehouse(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = warehouse_summary(db, current_user)
    return wrap_response(
        {"success": True, **body},
        db=db,
        data_origin="backend",
        read_only=True,
    )
