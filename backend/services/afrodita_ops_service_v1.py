"""
AFRODITA OPS v1 — vista unificada TPV + ERP (lectura), movimientos, rutas simuladas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.company import UserCompany
from app.models.erp import InventoryMovement, Product, TPVProduct
from app.models.user import User
from services.afrodita_unified_control import current_flags


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
        "read_only": not flags.get("execution_enabled", False) or bool(flags.get("read_only_mode")),
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
        "read_only": True,
    }


def simulate_route(deliveries: List[Dict[str, Any]], start_location: str) -> Dict[str, Any]:
    from agents.afrodita import Afrodita

    agent = Afrodita()
    raw = agent.optimize_route(deliveries, start_location)
    return {
        **raw,
        "simulated": True,
        "ui_badge": "SIMULADO",
        "note": "optimize_route es stub — AFRODITA_ENABLE_ROUTE_ENGINE=false",
    }
