"""
AFRODITA OPS v1 — inventario TPV+ERP, movimientos persistidos, rutas en BD.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.company import UserCompany
from app.models.erp import InventoryMovement, InventoryMovementType, Product, TPVProduct
from app.models.ops_route import OpsRoute
from app.models.user import User
from services.afrodita_unified_control import current_flags, get_global_status, writes_enabled
from services.workspace_deliverables import primary_company_id_for_user

logger = logging.getLogger(__name__)


def _company_ids(db: Session, user: User) -> List[int]:
    """Todas las empresas del usuario: solo para AUTORIZAR (p. ej. que un producto sea de una empresa de la
    que es miembro). Las LECTURAS de negocio usan `_session_company_ids` (solo la empresa de la sesion)."""
    rows = db.query(UserCompany.company_id).filter(UserCompany.user_id == user.id).all()
    return [int(r[0]) for r in rows]


def _session_company_ids(db: Session, user: User) -> List[int]:
    """[empresa de la sesion] (la misma que usa el chat / `company_inventory_status`) o [] si no tiene.
    Las vistas de inventario, movimientos y rutas nunca mezclan empresas: fail-closed sin empresa."""
    cid = primary_company_id_for_user(db, user)
    return [int(cid)] if cid else []


def _norm_key(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _match_keys(erp: Product, tpv: TPVProduct) -> bool:
    if _norm_key(erp.sku) == _norm_key(tpv.product_id):
        return True
    if _norm_key(erp.name) == _norm_key(tpv.name):
        return True
    return False


def _num_or_none(value: Any) -> Optional[float]:
    """NULL en BD = dato desconocido: se devuelve None (la UI muestra «—»), nunca 0 inventado."""
    return float(value) if value is not None else None


def _erp_row(p: Product) -> Dict[str, Any]:
    cat = p.category.value if hasattr(p.category, "value") else str(p.category or "")
    status = p.status.value if hasattr(p.status, "value") else str(p.status or "")
    return {
        "erp_id": p.id,
        "sku": p.sku,
        "name": p.name,
        "quantity_on_hand": _num_or_none(p.quantity_on_hand),
        # Minimo NULL = no se sabe cual es: None (la UI muestra «—»), no un 0 inventado.
        "low_stock_threshold": _num_or_none(p.low_stock_threshold),
        "track_inventory": bool(p.track_inventory),
        "category": cat,
        "status": status,
        "price": _num_or_none(p.price),
        "source": "erp",
    }


def _tpv_row(p: TPVProduct) -> Dict[str, Any]:
    return {
        "tpv_id": p.product_id,
        "name": p.name,
        "stock": p.stock,
        "category": p.category,
        "price": _num_or_none(p.price),
        "company_id": p.company_id,
        "source": "tpv",
    }


def list_erp_products(db: Session, *, company_ids: List[int], limit: int = 200) -> List[Dict[str, Any]]:
    """Productos ERP de las empresas indicadas. Fail-closed: sin empresas -> lista vacia."""
    if not company_ids:
        return []
    rows = (
        db.query(Product)
        .filter(Product.company_id.in_(company_ids))
        .order_by(Product.name.asc())
        .limit(limit)
        .all()
    )
    return [_erp_row(r) for r in rows]


def _session_tpv_rows(db: Session, user: User, *, limit: int = 500) -> List[TPVProduct]:
    """Productos TPV de la empresa de la sesion (antes: `user_id == user.id` OR cualquier empresa del
    usuario, que mezclaba empresas y arrastraba productos dados de alta en otro tenant)."""
    company_ids = _session_company_ids(db, user)
    if not company_ids:
        return []
    return (
        db.query(TPVProduct)
        .filter(TPVProduct.company_id.in_(company_ids))
        .order_by(TPVProduct.name.asc())
        .limit(limit)
        .all()
    )


def list_tpv_products(db: Session, user: User, *, limit: int = 500) -> List[Dict[str, Any]]:
    return [_tpv_row(r) for r in _session_tpv_rows(db, user, limit=limit)]


def merge_products_view(db: Session, user: User) -> Dict[str, Any]:
    flags = current_flags()
    global_mode = get_global_status(db)["execution_mode"]
    ui_badge = global_mode if global_mode in ("REAL", "SIMULATED", "ERROR") else "SIMULATED"
    company_ids = _session_company_ids(db, user)
    erp_items: List[Dict[str, Any]] = (
        list_erp_products(db, company_ids=company_ids) if flags["AFRODITA_USE_ERP"] else []
    )
    tpv_items: List[Dict[str, Any]] = list_tpv_products(db, user) if flags["AFRODITA_USE_TPV"] else []

    merged: List[Dict[str, Any]] = []
    used_tpv: set[int] = set()

    erp_rows: List[Product] = []
    if flags["AFRODITA_USE_ERP"] and company_ids:
        erp_rows = (
            db.query(Product)
            .filter(Product.company_id.in_(company_ids))
            .order_by(Product.name.asc())
            .limit(500)
            .all()
        )
    tpv_rows: List[TPVProduct] = _session_tpv_rows(db, user) if flags["AFRODITA_USE_TPV"] else []

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
        stock = erp_d["quantity_on_hand"]  # None = stock ERP desconocido (NULL), no 0
        if tpv_d and tpv_d.get("stock") is not None and (stock is None or stock == 0):
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
                # Stock ERP o minimo desconocidos (NULL) -> no se puede decir que este bajo minimos.
                "low_stock": bool(
                    erp_d["track_inventory"]
                    and erp_d["quantity_on_hand"] is not None
                    and erp_d["low_stock_threshold"] is not None
                    and erp_d["quantity_on_hand"] <= erp_d["low_stock_threshold"]
                ),
                "category": erp_d["category"],
                "price": erp_d["price"],
                "ui_badge": ui_badge,
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
                "ui_badge": ui_badge,
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


def list_inventory_movements(db: Session, user: User, *, limit: int = 100) -> Dict[str, Any]:
    """Movimientos de productos de la empresa de la sesion (fail-closed sin empresa)."""
    flags = current_flags()
    if not flags["AFRODITA_USE_ERP"]:
        return {"movements": [], "count": 0, "source": "inventory_movements", "read_only": True}

    company_ids = _session_company_ids(db, user)
    if not company_ids:
        return {"movements": [], "count": 0, "source": "inventory_movements", "read_only": not writes_enabled()}
    rows = (
        db.query(InventoryMovement, Product)
        .join(Product, Product.id == InventoryMovement.product_id)
        .filter(Product.company_id.in_(company_ids))
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
    if product.company_id is None:
        return None
    # Solo el gemelo TPV de la MISMA empresa que el producto ERP (antes: cualquier producto TPV del usuario
    # o de sus empresas con el mismo nombre/SKU, que podia mover el stock de otra empresa).
    q = db.query(TPVProduct).filter(TPVProduct.company_id == int(product.company_id))
    for tpv in q.all():
        if _match_keys(product, tpv):
            new_stock = int((tpv.stock or 0) + quantity_delta)
            tpv.stock = max(0, new_stock)
            return str(tpv.product_id)
    return None


def resolve_product_company_id(db: Session, user: User, product_id: int) -> int:
    """Empresa (de las del usuario) a la que pertenece el producto; si no es de ninguna -> 404."""
    company_ids = _company_ids(db, user)
    row = None
    if company_ids:
        row = (
            db.query(Product.company_id)
            .filter(Product.id == product_id, Product.company_id.in_(company_ids))
            .first()
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Producto {product_id} no encontrado")
    return int(row[0])


def create_inventory_movement(
    db: Session,
    user: User,
    *,
    product_id: int,
    movement_type: str,
    quantity: float,
    reference: Optional[str] = None,
    notes: Optional[str] = None,
    company_id: int,
) -> Dict[str, Any]:
    """`company_id` OBLIGATORIO (J9d): solo se opera sobre productos de esa empresa (otra empresa
    o producto sin empresa -> 404 sin revelar existencia). Los llamadores deben resolverlo en
    servidor (ver `resolve_product_company_id`), nunca desde el cliente sin validar."""
    flags = current_flags()
    if not flags.get("AFRODITA_USE_ERP"):
        raise HTTPException(status_code=503, detail="AFRODITA_USE_ERP=false")

    if company_id is None:
        raise HTTPException(status_code=404, detail=f"Producto {product_id} no encontrado")
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.company_id == int(company_id))
        .first()
    )
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


_ROUTE_DISTANCE_NOTE = (
    "Distancia y orden optimo no calculados: no hay servicio de rutas/geocodificacion "
    "integrado. Las paradas se guardan en el orden indicado."
)


def create_ops_route(
    db: Session,
    user: User,
    *,
    origin: str,
    destination: str,
    deliveries: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    # Antes: un stub de optimizacion devolvia 0 km y se rellenaba con una distancia
    # inventada (8/32 km + 4,2 km por parada). Ahora se guarda lo que de verdad se sabe.
    deliveries = deliveries or []
    stops = len(deliveries)
    distance = None

    company_id = primary_company_id_for_user(db, user)
    route_payload = {
        "origin": origin,
        "destination": destination,
        "stops": stops,
        "deliveries": deliveries,
        "optimized": False,
        "distance_km": None,
        "note": _ROUTE_DISTANCE_NOTE,
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

    try:
        from services.zeus_event_bus_v1 import emit_event

        emit_event(
            db,
            user,
            event_name="ops_route_created",
            source_module="AFRODITA_OPS",
            payload={
                "route_id": row.id,
                "origin": row.origin,
                "destination": row.destination,
                "owner_agent": "AFRODITA",
            },
        )
    except Exception:
        pass

    return {
        "route": {
            "id": row.id,
            "origin": row.origin,
            "destination": row.destination,
            "distance": row.distance,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "plan": route_payload,
        },
        "message": f"Ruta #{row.id} guardada ({stops} paradas). {_ROUTE_DISTANCE_NOTE}",
    }


def list_ops_routes(db: Session, user: User, *, limit: int = 50) -> Dict[str, Any]:
    company_ids = _session_company_ids(db, user)
    if not company_ids:
        return {"routes": [], "count": 0, "source": "ops_routes"}
    rows = (
        db.query(OpsRoute)
        .filter(OpsRoute.company_id.in_(company_ids))
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


def _qty_es(v: Any) -> str:
    """Cantidad en formato es-ES (sin decimales si es entera; coma decimal)."""
    f = float(v or 0)
    if f.is_integer():
        return f"{int(f):,}".replace(",", ".")
    return f"{f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".").rstrip("0").rstrip(",")


def company_inventory_status(db: Session, company_id: int, *, limit: int = 500) -> Dict[str, Any]:
    """Estado real del inventario de UNA empresa (la de la sesion): catalogo del TPV + productos ERP.

    - TPV (`tpv_products`, TPVProduct.company_id == company_id): es donde vive el catalogo real de
      hosteleria (el alta crea los productos TPV). `stock` NULL = el producto no lleva control de stock.
      El TPV no tiene campo de minimo: un producto solo TPV nunca se cuenta «bajo minimos».
    - ERP (`products`, Product.company_id == company_id): `track_inventory`, `quantity_on_hand` y
      `low_stock_threshold` (> 0 = minimo definido).
    - Sin duplicar: un producto ERP y uno TPV de la misma empresa con el mismo SKU/ID o nombre son UNA
      referencia (mismo emparejamiento `_match_keys` que la vista combinada y la sincronizacion de stock).
      Si el ERP lleva el control de stock manda el ERP (precedencia de `merge_products_view`); si no,
      se usa el stock del TPV.
    """
    flags = current_flags()
    use_tpv, use_erp = bool(flags.get("AFRODITA_USE_TPV")), bool(flags.get("AFRODITA_USE_ERP"))
    if not use_tpv and not use_erp:
        raise HTTPException(status_code=503, detail="AFRODITA_USE_TPV=false y AFRODITA_USE_ERP=false")
    cap = min(limit, 500)
    tpv_rows: List[TPVProduct] = (
        db.query(TPVProduct).filter(TPVProduct.company_id == company_id)
        .order_by(TPVProduct.name.asc()).limit(cap).all()
        if use_tpv else []
    )
    erp_rows: List[Product] = (
        db.query(Product).filter(Product.company_id == company_id)
        .order_by(Product.name.asc()).limit(cap).all()
        if use_erp else []
    )

    items: List[Dict[str, Any]] = []
    used_tpv: set[int] = set()
    for erp in erp_rows:
        twin: Optional[TPVProduct] = None
        for idx, tpv in enumerate(tpv_rows):
            if idx not in used_tpv and _match_keys(erp, tpv):
                twin = tpv
                used_tpv.add(idx)
                break
        if erp.track_inventory and erp.quantity_on_hand is not None:
            stock: Optional[float] = float(erp.quantity_on_hand)
        elif twin is not None and twin.stock is not None:
            # ERP sin control de stock, o con control pero cantidad NULL (desconocida): manda el TPV si la sabe
            stock = float(twin.stock)
        else:
            stock = None
        # Minimo NULL (desconocido) o 0 = «sin minimo»: min_stock None, nunca cuenta como bajo minimos.
        threshold = _num_or_none(erp.low_stock_threshold) if erp.track_inventory else None
        items.append({
            # nombre recortado (igual que el emparejamiento `_match_keys`): «Harina » sale como «Harina»
            "sku": (erp.sku or "").strip() or None, "name": (erp.name or "").strip(), "stock": stock,
            "min_stock": threshold if threshold is not None and threshold > 0 else None,
            "source": "tpv+erp" if twin is not None else "erp",
        })
    for idx, tpv in enumerate(tpv_rows):
        if idx in used_tpv:
            continue
        items.append({
            "sku": None, "name": (tpv.name or "").strip(),
            "stock": float(tpv.stock) if tpv.stock is not None else None,
            "min_stock": None, "source": "tpv",
        })
    items.sort(key=lambda i: (i["name"] or "").lower())

    tracked = [i for i in items if i["stock"] is not None]
    untracked = [i for i in items if i["stock"] is None]
    out = [i for i in tracked if i["stock"] <= 0]
    low = [i for i in tracked if i["stock"] > 0 and i["min_stock"] is not None and i["stock"] <= i["min_stock"]]
    top = sorted((i for i in tracked if i["stock"] > 0), key=lambda i: (-i["stock"], (i["name"] or "").lower()))

    def _brief(i: Dict[str, Any], with_min: bool = False) -> Dict[str, Any]:
        d: Dict[str, Any] = {"name": i["name"], "stock": i["stock"]}
        if i["sku"]:
            d["sku"] = i["sku"]
        if with_min:
            d["min_stock"] = i["min_stock"]
        return d

    result = {
        "company_id": company_id,
        "total_skus": len(items),
        "tracked_skus": len(tracked),
        "out_of_stock_count": len(out),
        "low_stock_count": len(low),
        "untracked_skus": len(untracked),
        "without_min_count": sum(1 for i in tracked if i["min_stock"] is None),
        "total_units": round(sum(i["stock"] for i in tracked), 2),
        "out_of_stock_items": [_brief(i) for i in out[:20]],
        "low_stock_items": [_brief(i, with_min=True) for i in low[:20]],
        "top_items": [_brief(i) for i in top[:5]],
        "untracked_items": [{"name": i["name"]} for i in untracked[:20]],
        "items": items,
        "tpv_products": len(tpv_rows),
        "erp_products": len(erp_rows),
        "sources": [s for s, on in (("tpv_products", use_tpv), ("products", use_erp)) if on],
    }
    logger.info(
        "afrodita_inventory_status company_id=%s refs=%s tracked=%s out=%s low=%s untracked=%s tpv=%s erp=%s",
        company_id, len(items), len(tracked), len(out), len(low), len(untracked), len(tpv_rows), len(erp_rows),
    )
    return result


def _stock_names(lst: List[Dict[str, Any]], with_min: bool = False, shown: int = 5) -> str:
    """«Nombre (cantidad)» o «Nombre (cantidad, mínimo M)» de los primeros `shown` productos."""
    parts = []
    for i in lst[:shown]:
        q = _qty_es(i.get("stock"))
        parts.append(f"{i.get('name')} ({q}, mínimo {_qty_es(i.get('min_stock'))})" if with_min
                     else f"{i.get('name')} ({q})")
    return ", ".join(parts)


def _with_min_count(inv: Dict[str, Any]) -> int:
    """Productos con control de stock Y minimo definido: los unicos de los que se puede decir si estan
    bajo minimos (sin minimo, «ninguno bajo minimos» seria inventado)."""
    return max(int(inv.get("tracked_skus") or 0) - int(inv.get("without_min_count") or 0), 0)


def inventory_status_text(inv: Dict[str, Any]) -> str:
    """Respuesta en espanol (es-ES) con los datos reales de `company_inventory_status`; el vacio es un dato."""
    total = int(inv.get("total_skus") or 0)
    if not total:
        return "No tienes productos dados de alta en el TPV ni en el inventario de tu empresa."
    tracked = int(inv.get("tracked_skus") or 0)
    untracked = int(inv.get("untracked_skus") or 0)
    refs = "1 referencia" if total == 1 else f"{total} referencias"
    if not tracked:
        return (f"Inventario: {refs}, pero ninguna lleva control de stock (no tienen stock indicado en el TPV), "
                "así que no puedo decirte cuántas unidades te quedan.")

    head = f"Inventario: {refs}"
    if untracked:
        head += f" ({tracked} con control de stock y {untracked} sin control de stock)"
    head += f", {_qty_es(inv.get('total_units'))} unidades en stock."
    out_n = int(inv.get("out_of_stock_count") or 0)
    low_n = int(inv.get("low_stock_count") or 0)
    with_min = _with_min_count(inv)
    parts = [head]
    parts.append(f" Sin stock: {out_n} ({_stock_names(inv.get('out_of_stock_items') or [])})." if out_n
                 else " Ninguna sin stock.")
    if low_n:
        parts.append(f" Bajo mínimos: {low_n} ({_stock_names(inv.get('low_stock_items') or [], with_min=True)}).")
    elif not with_min:
        # sin ningun minimo definido no se sabe si algo esta bajo minimos: decirlo, no «ninguna»
        parts.append(" No puedo saber cuáles están bajo mínimos porque ninguna tiene mínimo definido.")
    else:
        parts.append(f" Ninguna bajo mínimos (de las {with_min} con mínimo definido)." if with_min > 1
                     else " Ninguna bajo mínimos (de la única con mínimo definido).")
    nomin = int(inv.get("without_min_count") or 0)
    if nomin and with_min:
        parts.append(f" {nomin} sin mínimo definido.")
    top = inv.get("top_items") or []
    if top:
        parts.append(f" Más stock: {_stock_names(top)}.")
    return "".join(parts)


# Consultas de alerta de stock del chat («productos sin stock», «¿algo bajo mínimos?», «¿qué me falta?»):
# "out" = agotados, "low" = bajo minimos / poco stock, "alerts" = ambas cosas.
INVENTORY_FOCUS = ("out", "low", "alerts")
# + "product": stock de UN producto (`product_stock_text`), con el nombre pedido en `product`
INVENTORY_READ_FOCUS = INVENTORY_FOCUS + ("product",)


def inventory_alerts_text(inv: Dict[str, Any], focus: str) -> str:
    """Respuesta a una consulta de ALERTA de stock con los datos reales de `company_inventory_status`.
    Honesta: si ningun producto lleva control de stock, o ninguno tiene minimo definido, lo dice (nunca
    «ninguno bajo minimos» sin minimos). Los productos sin control de stock se mencionan: de esos no se sabe."""
    if focus not in INVENTORY_FOCUS:
        raise ValueError("focus no valido")
    total = int(inv.get("total_skus") or 0)
    if not total:
        return ("No tienes productos dados de alta en el TPV ni en el inventario de tu empresa, así que no puedo "
                "decirte qué falta.")
    tracked = int(inv.get("tracked_skus") or 0)
    untracked = int(inv.get("untracked_skus") or 0)
    if not tracked:
        refs = ("1 referencia, pero no lleva control de stock (no tiene" if total == 1
                else f"{total} referencias, pero ninguna lleva control de stock (no tienen")
        return (f"Inventario: {refs} stock indicado en el TPV ni en el inventario), así que no puedo saber qué se "
                "ha agotado ni qué está bajo mínimos.")
    out_n = int(inv.get("out_of_stock_count") or 0)
    low_n = int(inv.get("low_stock_count") or 0)
    with_min = _with_min_count(inv)
    nomin = int(inv.get("without_min_count") or 0)

    def _list(n: int, items: List[Dict[str, Any]], with_min_: bool = False) -> str:
        more = f" y {n - 5} más" if n > 5 else ""
        return f"{_stock_names(items, with_min=with_min_)}{more}"

    parts: List[str] = []
    if focus in ("out", "alerts"):
        if out_n:
            parts.append(f"Sin stock: {out_n} ({_list(out_n, inv.get('out_of_stock_items') or [])}).")
        else:
            parts.append("Ningún producto con control de stock está agotado." if tracked > 1
                         else "Tu único producto con control de stock no está agotado.")
    if focus in ("low", "alerts"):
        if not with_min:
            parts.append("No puedo saber qué está bajo mínimos porque ningún producto tiene mínimo definido.")
        elif low_n:
            parts.append(f"Bajo mínimos: {low_n} "
                         f"({_list(low_n, inv.get('low_stock_items') or [], with_min_=True)}).")
        else:
            parts.append(f"Ninguno de los {with_min} productos con mínimo definido está bajo mínimos."
                         if with_min > 1 else "El único producto con mínimo definido no está bajo mínimos.")
        if with_min and nomin:
            parts.append(f"{nomin} con control de stock no tienen mínimo definido." if nomin > 1
                         else "1 con control de stock no tiene mínimo definido.")
        if focus == "low" and out_n:
            parts.append(f"Además, sin stock: {out_n} ({_list(out_n, inv.get('out_of_stock_items') or [])}).")
    if untracked:
        parts.append(f"{untracked} productos no llevan control de stock: de esos no sé cuántas unidades quedan."
                     if untracked > 1 else
                     "1 producto no lleva control de stock: de ese no sé cuántas unidades quedan.")
    return " ".join(parts)


# Stock de UN producto («¿me queda cerveza?», «¿cuánto stock queda de harina?»): se busca en los productos de
# `company_inventory_status` (empresa de la sesion), sin acentos ni mayusculas, admitiendo singular/plural y
# el nombre de pila del producto («vino» -> «Vino tinto»). Nunca se inventa: si no esta, se dice.
_PRODUCT_ARTICLES = ("el ", "la ", "los ", "las ", "un ", "una ", "unos ", "unas ")


def _product_key(value: Any) -> str:
    from services.intent_parser import fold

    return fold(" ".join(str(value or "").split())).strip()


def _product_variants(product: str) -> set:
    p = _product_key(product)
    for art in _PRODUCT_ARTICLES:
        if p.startswith(art):
            p = p[len(art):]
            break
    out = {p, p + "s", p + "es"}
    if p.endswith("es") and len(p) > 4:
        out.add(p[:-2])
    if p.endswith("s") and len(p) > 3:
        out.add(p[:-1])
    return {v for v in out if v}


def match_inventory_items(items: List[Dict[str, Any]], product: str) -> List[Dict[str, Any]]:
    """Productos del inventario cuyo nombre es `product` (o empieza por el: «vino» -> «Vino tinto»)."""
    variants = _product_variants(product)
    if not variants:
        return []
    exact = [i for i in items if _product_key(i.get("name")) in variants]
    if exact:
        return exact
    return [i for i in items if any(_product_key(i.get("name")).startswith(v + " ") for v in variants)]


def product_stock_text(inv: Dict[str, Any], product: str) -> str:
    """Stock real de los productos que coinciden con `product` en el inventario de la empresa de la sesion."""
    found = match_inventory_items(inv.get("items") or [], product)
    if not found:
        return f"No encuentro «{' '.join(str(product or '').split())}» en tu inventario."
    parts = []
    for i in found[:5]:
        name, stock, mn = i.get("name"), i.get("stock"), i.get("min_stock")
        if stock is None:
            parts.append(f"{name} no lleva control de stock, así que no sé cuántas unidades quedan.")
            continue
        q = _qty_es(stock)
        units = "unidad" if float(stock) == 1 else "unidades"
        if stock <= 0:
            parts.append(f"{name}: sin stock (0 unidades).")
        elif mn is not None and stock <= mn:
            parts.append(f"{name}: quedan {q} {units} (mínimo {_qty_es(mn)}: bajo mínimos).")
        elif mn is not None:
            parts.append(f"{name}: quedan {q} {units} (mínimo {_qty_es(mn)}).")
        else:
            parts.append(f"{name}: quedan {q} {units}.")
    if len(found) > 5:
        parts.append(f"Y {len(found) - 5} productos más con ese nombre.")
    return " ".join(parts)
