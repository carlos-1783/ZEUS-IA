"""
AFRODITA OPS v1 — inventario TPV+ERP, movimientos persistidos, rutas en BD.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.company import UserCompany
from app.models.erp import InventoryMovement, InventoryMovementType, Product, TPVProduct
from app.models.ops_route import OpsRoute
from app.models.user import User
from services.afrodita_unified_control import current_flags, writes_enabled
from services.workspace_deliverables import primary_company_id_for_user

logger = logging.getLogger(__name__)


def _company_ids(db: Session, user: User) -> List[int]:
    rows = db.query(UserCompany.company_id).filter(UserCompany.user_id == user.id).all()
    return [int(r[0]) for r in rows]


def _norm_key(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _match_keys(erp: Product, tpv: TPVProduct) -> bool:
    if _norm_key(erp.sku) == _norm_key(tpv.product_id):
        return True
    if _norm_key(erp.name) == _norm_key(tpv.name):
        return True
    return False


def _erp_row(p: Product) -> Dict[str, Any]:
    cat = p.category.value if hasattr(p.category, "value") else str(p.category or "")
    status = p.status.value if hasattr(p.status, "value") else str(p.status or "")
    return {
        "erp_id": p.id,
        "sku": p.sku,
        "name": p.name,
        "quantity_on_hand": float(p.quantity_on_hand or 0),
        "low_stock_threshold": float(p.low_stock_threshold or 0),
        "track_inventory": bool(p.track_inventory),
        "category": cat,
        "status": status,
        "price": float(p.price or 0),
        "source": "erp",
    }


def _tpv_row(p: TPVProduct) -> Dict[str, Any]:
    return {
        "tpv_id": p.product_id,
        "name": p.name,
        "stock": p.stock,
        "category": p.category,
        "price": float(p.price or 0),
        "company_id": p.company_id,
        "source": "tpv",
    }


def list_erp_products(db: Session, *, limit: int = 200) -> List[Dict[str, Any]]:
    rows = db.query(Product).order_by(Product.name.asc()).limit(limit).all()
    return [_erp_row(r) for r in rows]


def list_tpv_products(db: Session, user: User, *, limit: int = 500) -> List[Dict[str, Any]]:
    company_ids = _company_ids(db, user)
    q = db.query(TPVProduct)
    if company_ids:
        q = q.filter(
            or_(
                TPVProduct.user_id == user.id,
                TPVProduct.company_id.in_(company_ids),
            )
        )
    else:
        q = q.filter(TPVProduct.user_id == user.id)
    rows = q.order_by(TPVProduct.name.asc()).limit(limit).all()
    return [_tpv_row(r) for r in rows]


def merge_products_view(db: Session, user: User) -> Dict[str, Any]:
    flags = current_flags()
    erp_items: List[Dict[str, Any]] = list_erp_products(db) if flags["AFRODITA_USE_ERP"] else []
    tpv_items: List[Dict[str, Any]] = list_tpv_products(db, user) if flags["AFRODITA_USE_TPV"] else []

    merged: List[Dict[str, Any]] = []
    used_tpv: set[int] = set()

    erp_rows = db.query(Product).order_by(Product.name.asc()).limit(500).all() if flags["AFRODITA_USE_ERP"] else []
    tpv_rows: List[TPVProduct] = []
    if flags["AFRODITA_USE_TPV"]:
        company_ids = _company_ids(db, user)
        q = db.query(TPVProduct)
        if company_ids:
            q = q.filter(
                or_(
                    TPVProduct.user_id == user.id,
                    TPVProduct.company_id.in_(company_ids),
                )
            )
        else:
            q = q.filter(TPVProduct.user_id == user.id)
        tpv_rows = q.order_by(TPVProduct.name.asc()).limit(500).all()

    for erp in erp_rows:
        erp_d = _erp_row(erp)
        tpv_match: Optional[TPVProduct] = None
        for idx, tpv in enumerate(tpv_rows):
            if idx in used_tpv:
                continue
            if _match_keys(erp, tpv):
                tpv_match = tpv
                used_tpv.add(idx)
                break
        tpv_d = _tpv_row(tpv_match) if tpv_match else None
        stock = erp_d["quantity_on_hand"]
        if tpv_d and tpv_d.get("stock") is not None and stock == 0:
            stock = float(tpv_d["stock"])
        merged.append(
            {
                "id": erp_d["sku"],
                "product_id": erp_d["erp_id"],
                "name": erp_d["name"],
                "source": "merged" if tpv_d else "erp",
                "stock": stock,
                "erp_quantity_on_hand": erp_d["quantity_on_hand"],
                "tpv_stock": tpv_d["stock"] if tpv_d else None,
                "low_stock": bool(
                    erp_d["track_inventory"]
                    and erp_d["quantity_on_hand"] <= erp_d["low_stock_threshold"]
                ),
                "category": erp_d["category"],
                "price": erp_d["price"],
                "ui_badge": "REAL",
            }
        )

    for idx, tpv in enumerate(tpv_rows):
        if idx in used_tpv:
            continue
        tpv_d = _tpv_row(tpv)
        merged.append(
            {
                "id": tpv_d["tpv_id"],
                "product_id": None,
                "name": tpv_d["name"],
                "source": "tpv",
                "stock": float(tpv_d["stock"]) if tpv_d["stock"] is not None else None,
                "erp_quantity_on_hand": None,
                "tpv_stock": tpv_d["stock"],
                "low_stock": False,
                "category": tpv_d["category"],
                "price": tpv_d["price"],
                "ui_badge": "REAL",
            }
        )

    return {
        "items": merged,
        "count": len(merged),
        "erp_count": len(erp_items),
        "tpv_count": len(tpv_items),
        "precedence": "erp",
        "read_only": not writes_enabled(),
    }


def list_inventory_movements(db: Session, *, limit: int = 100) -> Dict[str, Any]:
    flags = current_flags()
    if not flags["AFRODITA_USE_ERP"]:
        return {"movements": [], "count": 0, "source": "inventory_movements", "read_only": True}

    rows = (
        db.query(InventoryMovement, Product)
        .join(Product, Product.id == InventoryMovement.product_id)
        .order_by(InventoryMovement.created_at.desc())
        .limit(min(limit, 500))
        .all()
    )
    movements = []
    for mov, prod in rows:
        mtype = mov.movement_type.value if hasattr(mov.movement_type, "value") else str(mov.movement_type)
        movements.append(
            {
                "id": mov.id,
                "product_id": mov.product_id,
                "product_name": prod.name,
                "product_sku": prod.sku,
                "movement_type": mtype,
                "quantity": float(mov.quantity or 0),
                "reference": mov.reference,
                "notes": mov.notes,
                "created_at": mov.created_at.isoformat() if mov.created_at else None,
            }
        )
    return {
        "movements": movements,
        "count": len(movements),
        "source": "inventory_movements",
        "read_only": not writes_enabled(),
    }


def _parse_movement_type(raw: str) -> InventoryMovementType:
    key = (raw or "adjustment").strip().lower()
    try:
        return InventoryMovementType(key)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"movement_type inválido: {raw}",
        )


def _sync_tpv_stock_for_product(
    db: Session,
    user: User,
    product: Product,
    quantity_delta: float,
) -> Optional[str]:
    flags = current_flags()
    if not flags.get("AFRODITA_USE_TPV"):
        return None
    company_ids = _company_ids(db, user)
    q = db.query(TPVProduct)
    if company_ids:
        q = q.filter(
            or_(
                TPVProduct.user_id == user.id,
                TPVProduct.company_id.in_(company_ids),
            )
        )
    else:
        q = q.filter(TPVProduct.user_id == user.id)
    for tpv in q.all():
        if _match_keys(product, tpv):
            new_stock = int((tpv.stock or 0) + quantity_delta)
            tpv.stock = max(0, new_stock)
            return str(tpv.product_id)
    return None


def create_inventory_movement(
    db: Session,
    user: User,
    *,
    product_id: int,
    movement_type: str,
    quantity: float,
    reference: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    flags = current_flags()
    if not flags.get("AFRODITA_USE_ERP"):
        raise HTTPException(status_code=503, detail="AFRODITA_USE_ERP=false")

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Producto {product_id} no encontrado")
    if not product.track_inventory:
        raise HTTPException(status_code=422, detail="El producto no tiene track_inventory activo")

    mtype = _parse_movement_type(movement_type)
    qty = float(quantity)
    if qty == 0:
        raise HTTPException(status_code=422, detail="quantity no puede ser 0")

    new_stock = float(product.quantity_on_hand or 0) + qty
    if new_stock < 0:
        raise HTTPException(status_code=422, detail="Stock resultante negativo")

    movement = InventoryMovement(
        product_id=product.id,
        movement_type=mtype,
        quantity=qty,
        reference=(reference or "afrodita_ops_v1")[:100],
        notes=notes,
        created_by=user.id,
    )
    product.quantity_on_hand = new_stock
    db.add(movement)
    db.flush()

    tpv_id = _sync_tpv_stock_for_product(db, user, product, qty)
    db.refresh(movement)

    logger.info(
        "[AFRODITA_OPS] movement id=%s product=%s qty=%s stock=%s",
        movement.id,
        product_id,
        qty,
        product.quantity_on_hand,
    )
    return {
        "movement": {
            "id": movement.id,
            "product_id": product.id,
            "product_name": product.name,
            "product_sku": product.sku,
            "movement_type": mtype.value,
            "quantity": qty,
            "reference": movement.reference,
            "notes": movement.notes,
            "created_at": movement.created_at.isoformat() if movement.created_at else None,
        },
        "stock_after": float(product.quantity_on_hand or 0),
        "tpv_synced": tpv_id,
        "message": f"Movimiento registrado — stock ERP: {product.quantity_on_hand}",
    }


def _estimate_route_distance(origin: str, destination: str, stops: int) -> float:
    o = (origin or "").strip().lower()
    d = (destination or "").strip().lower()
    base = 8.0 if o == d else 32.0
    return round(base + max(stops, 1) * 4.2, 2)


def create_ops_route(
    db: Session,
    user: User,
    *,
    origin: str,
    destination: str,
    deliveries: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    from agents.afrodita import Afrodita

    deliveries = deliveries or []
    agent = Afrodita()
    plan = agent.optimize_route(deliveries, origin)
    stops = len(deliveries)
    distance = float(plan.get("estimated_distance_km") or 0)
    if distance <= 0:
        distance = _estimate_route_distance(origin, destination, stops)

    company_id = primary_company_id_for_user(db, user)
    route_payload = {
        **plan,
        "origin": origin,
        "destination": destination,
        "stops": stops,
        "distance_km": distance,
    }
    row = OpsRoute(
        user_id=user.id,
        company_id=company_id,
        origin=origin[:255],
        destination=destination[:255],
        distance=distance,
        route_json=json.dumps(route_payload, ensure_ascii=False),
    )
    db.add(row)
    db.flush()
    db.refresh(row)

    return {
        "route": {
            "id": row.id,
            "origin": row.origin,
            "destination": row.destination,
            "distance": row.distance,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "plan": route_payload,
        },
        "message": f"Ruta persistida ({distance} km)",
    }


def list_ops_routes(db: Session, user: User, *, limit: int = 50) -> Dict[str, Any]:
    rows = (
        db.query(OpsRoute)
        .filter(OpsRoute.user_id == user.id)
        .order_by(OpsRoute.id.desc())
        .limit(min(limit, 200))
        .all()
    )
    routes = []
    for r in rows:
        plan: Dict[str, Any] = {}
        if r.route_json:
            try:
                plan = json.loads(r.route_json)
            except json.JSONDecodeError:
                plan = {}
        routes.append(
            {
                "id": r.id,
                "origin": r.origin,
                "destination": r.destination,
                "distance": r.distance,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "plan": plan,
            }
        )
    return {"routes": routes, "count": len(routes), "source": "ops_routes"}


def warehouse_summary(db: Session, user: User) -> Dict[str, Any]:
    inv = merge_products_view(db, user)
    items = inv.get("items") or []
    low_stock = [i for i in items if i.get("low_stock")]
    total_units = sum(float(i.get("stock") or 0) for i in items)
    locations = [
        {
            "code": "MAIN",
            "label": "Almacén principal",
            "sku_count": len(items),
            "units_on_hand": round(total_units, 2),
            "low_stock_skus": len(low_stock),
        }
    ]
    return {
        "implemented": True,
        "locations": locations,
        "total_skus": len(items),
        "low_stock_count": len(low_stock),
        "total_units": round(total_units, 2),
        "low_stock_items": [
            {"id": i.get("id"), "name": i.get("name"), "stock": i.get("stock")} for i in low_stock[:20]
        ],
        "read_only": not writes_enabled(),
    }
