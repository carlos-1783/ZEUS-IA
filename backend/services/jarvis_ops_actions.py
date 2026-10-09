"""J9e: acciones reales de JUSTICIA y AFRODITA expuestas en el chat JARVIS.

Las CONSULTAS (estado legal, auditoria de cumplimiento, inventario) se ejecutan sin confirmacion
por el EJECUTOR de agentes (`zeus_agent_executor_v1.execute_agent_action`): mismo guard THALOS,
mismo control de modulos y mismo ambito de empresa que la API, sin duplicar logica.

Las ESCRITURAS (ruta operativa, movimiento de inventario) solo se PREPARAN aqui: validan el payload
con `_clean_afrodita_payload` (la misma funcion que usa el ejecutor), resuelven el producto EN LA EMPRESA
DEL USUARIO (nombre/SKU exactos + `resolve_product_company_id`) y devuelven la vista previa. La
aprobacion humana (J3b), el rol y la ejecucion los hace el orquestador/ejecutor como siempre.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.zeus_action import ZeusAction
from app.schemas.zeus_task import ZeusExecutionResult

logger = logging.getLogger(__name__)

# accion del chat -> (accion del ejecutor, agente). `shift_status` ya tenia handler propio del chat.
READ_ACTIONS: Dict[str, Tuple[str, str]] = {
    "get_legal_status": ("get_legal_status", "JUSTICIA"),
    "run_compliance_audit": ("run_compliance_audit", "JUSTICIA"),
    "get_inventory_status": ("get_inventory_status", "AFRODITA"),
}
WRITE_ACTIONS = frozenset({"create_ops_route", "create_inventory_movement"})
# Consultas que un paso de plan puede ejecutar (nombre del ejecutor -> (accion del chat, agente)).
PLAN_READ_ACTIONS: Dict[str, Tuple[str, str]] = {
    "get_legal_status": ("get_legal_status", "JUSTICIA"),
    "run_compliance_audit": ("run_compliance_audit", "JUSTICIA"),
    "get_inventory_status": ("get_inventory_status", "AFRODITA"),
    "get_shift_status": ("shift_status", "AFRODITA"),
}


def _format_read(chat_action: str, result: Dict[str, Any]) -> str:
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    if chat_action == "get_legal_status" and "legal_documents" in data:
        pend = data.get("pending")
        extra = f" Pendientes de revisión: {len(pend)} grupos." if isinstance(pend, (list, dict)) and pend else ""
        return (f"Estado legal de tu cuenta: {data['legal_documents']} documentos legales y "
                f"{data.get('compliance_events', 0)} eventos de cumplimiento registrados.{extra}")
    if chat_action == "get_inventory_status" and "total_skus" in data:
        low = data.get("low_stock_items") or []
        names = ", ".join(f"{i.get('name')} ({i.get('stock'):g})" for i in low[:5] if isinstance(i.get("stock"), (int, float)))
        tail = f" Stock bajo: {names}." if names else ""
        return (f"Inventario: {data['total_skus']} referencias, {data.get('total_units', 0):g} unidades en total, "
                f"{data.get('low_stock_count', 0)} con stock bajo.{tail}")
    return str(result.get("message") or "")


async def run_read_action(db: Session, user: User, action: ZeusAction) -> ZeusExecutionResult:
    """Ejecuta una consulta real via ejecutor. Nunca crea aprobaciones. Errores -> resultado fallido."""
    from services.zeus_agent_executor_v1 import execute_agent_action

    exec_name, agent = READ_ACTIONS[action.action_type]
    try:
        out = await execute_agent_action(db, user=user, agent=agent, action=exec_name, payload={})
    except HTTPException as exc:
        db.rollback()
        return ZeusExecutionResult(success=False, intent=action.action_type, message=str(exc.detail), executed=False)
    except Exception:
        db.rollback()
        logger.exception("jarvis_ops: fallo ejecutando %s", exec_name)
        return ZeusExecutionResult(
            success=False, intent=action.action_type, executed=False,
            message="No se pudo completar la consulta; inténtalo de nuevo.",
        )
    ok = bool(out.get("success")) and bool(out.get("executed"))
    return ZeusExecutionResult(
        success=ok, intent=action.action_type, executed=ok,
        message=_format_read(action.action_type, out) if ok else str(out.get("message") or "No se pudo completar la consulta."),
        metrics=out.get("data") if isinstance(out.get("data"), dict) else {},
        company_id=out.get("company_id"),
    )


def resolve_product(db: Session, user: User, company_id: int, text: str) -> Tuple[Optional[Any], Optional[str]]:
    """Producto de la empresa por nombre o SKU EXACTOS (sin acentos/mayusculas). -> (producto, error).
    Ambiguo o inexistente -> error (nunca se adivina). Un producto de otra empresa no existe aqui."""
    from app.models.erp import Product
    from services import intent_parser as ip
    from services.afrodita_ops_service_v1 import resolve_product_company_id

    want = ip.fold(" ".join((text or "").split()))
    if not want:
        return None, "No he entendido qué producto es."
    base = db.query(Product).filter(Product.company_id == company_id)
    rows = base.filter(or_(func.lower(Product.name) == want, func.lower(Product.sku) == want)).all()
    if not rows:
        rows = [p for p in base.limit(5000).all()
                if ip.fold(" ".join((p.name or "").split())) == want or ip.fold(p.sku or "") == want]
    if not rows:
        return None, f"No encuentro el producto «{text}» en tu empresa. No he preparado nada."
    if len(rows) > 1:
        return None, f"Hay varios productos que coinciden con «{text}»; indica el SKU exacto. No he preparado nada."
    product = rows[0]
    try:
        if resolve_product_company_id(db, user, product.id) != company_id:
            raise HTTPException(status_code=404, detail="no coincide")
    except HTTPException:
        return None, f"No encuentro el producto «{text}» en tu empresa. No he preparado nada."
    return product, None


def prepare_write(db: Session, user: User, action: ZeusAction) -> Tuple[Optional[Dict[str, Any]], str]:
    """Valida y normaliza la escritura. -> (payload_limpio, mensaje_vista_previa) o (None, motivo).
    Reutiliza `_clean_afrodita_payload` del ejecutor (misma validacion que tras la aprobacion)."""
    from services.zeus_agent_executor_v1 import _afrodita_writes_blocked, _clean_afrodita_payload

    cid = action.company_id
    if cid is None:
        return None, "Tu usuario no tiene empresa asociada. No he preparado nada."
    wb = _afrodita_writes_blocked()
    if wb:
        return None, wb["message"]
    p = action.payload or {}
    if action.action_type == "create_ops_route":
        raw = {"origin": p.get("origin"), "destination": p.get("destination"), "deliveries": []}
    else:
        product, err = resolve_product(db, user, cid, str(p.get("product_text") or ""))
        if product is None:
            return None, err or "Producto no encontrado."
        qty = float(p.get("quantity") or 0)
        if p.get("movement") == "out":
            qty = -abs(qty)
            mtype = "sale"
        else:
            qty = abs(qty)
            mtype = "purchase"
        raw = {"product_id": product.id, "movement_type": mtype, "quantity": qty, "reference": "jarvis_chat"}
    clean, msg = _clean_afrodita_payload(db, action.action_type, raw, cid)
    if clean is None:
        return None, f"{msg} No he preparado nada."
    return clean, msg
