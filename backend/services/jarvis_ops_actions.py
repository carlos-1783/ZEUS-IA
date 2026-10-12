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
    "get_security_status": ("get_security_status", "THALOS"),
    "track_leads": ("track_leads", "PERSEO"),
    "get_daily_close": ("get_daily_close", "RAFAEL"),
    "get_pending_invoices": ("get_pending_invoices", "RAFAEL"),
    "get_sales_performance": ("get_sales_performance", "PERSEO"),
    "get_attendance_status": ("get_attendance_status", "AFRODITA"),
    "get_today_agenda": ("get_today_agenda", "AFRODITA"),
    "get_weekly_orders": ("get_weekly_orders", "AFRODITA"),
    "review_contracts": ("review_contracts", "JUSTICIA"),
}
# Claves del payload del chat que cada consulta puede pasar al ejecutor (lista blanca; el resto
# del payload del chat, contexto incluido, nunca llega al ejecutor).
READ_PAYLOAD_KEYS: Dict[str, Tuple[str, ...]] = {
    "get_daily_close": ("day",),
    "get_sales_performance": ("days",),
}
WRITE_ACTIONS = frozenset({"create_ops_route", "create_inventory_movement"})
# Consultas que un paso de plan puede ejecutar (nombre del ejecutor -> (accion del chat, agente)).
PLAN_READ_ACTIONS: Dict[str, Tuple[str, str]] = {
    "get_legal_status": ("get_legal_status", "JUSTICIA"),
    "run_compliance_audit": ("run_compliance_audit", "JUSTICIA"),
    "get_inventory_status": ("get_inventory_status", "AFRODITA"),
    "get_shift_status": ("shift_status", "AFRODITA"),
    "get_security_status": ("get_security_status", "THALOS"),
    "track_leads": ("track_leads", "PERSEO"),
    "get_daily_close": ("get_daily_close", "RAFAEL"),
    "get_pending_invoices": ("get_pending_invoices", "RAFAEL"),
    "get_sales_performance": ("get_sales_performance", "PERSEO"),
    "get_attendance_status": ("get_attendance_status", "AFRODITA"),
    "get_today_agenda": ("get_today_agenda", "AFRODITA"),
    "review_contracts": ("review_contracts", "JUSTICIA"),
}


def _eur(v: Any) -> str:
    return f"{float(v or 0):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_read(chat_action: str, result: Dict[str, Any]) -> str:
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    if chat_action == "get_legal_status" and "legal_documents" in data:
        pend = data.get("pending")
        extra = f" Pendientes de revisión: {len(pend)} grupos." if isinstance(pend, (list, dict)) and pend else ""
        return (f"Estado legal de tu cuenta: {data['legal_documents']} documentos legales y "
                f"{data.get('compliance_events', 0)} eventos de cumplimiento registrados.{extra}")
    if chat_action == "get_daily_close" and "tickets" in data:
        if not data["tickets"]:
            return f"No hay ventas TPV registradas el {data['date']} en tu empresa. {data['note']}"
        methods = ", ".join(f"{m} {_eur(v['total'])} ({v['count']})" for m, v in data["by_payment_method"].items())
        return (f"Cierre del {data['date']}: {data['tickets']} tickets, total {_eur(data['total'])} "
                f"(IVA {_eur(data['tax_total'])}, ticket medio {_eur(data['average_ticket'])}). "
                f"Por forma de pago: {methods}. {data['note']}")
    if chat_action == "get_pending_invoices" and "pending_count" in data:
        drafts = f" Además tienes {data['drafts_count']} borrador(es) sin emitir." if data["drafts_count"] else ""
        if not data["pending_count"]:
            return f"No tienes facturas pendientes de cobro.{drafts}"
        over = (f", {data['overdue_count']} vencida(s) por {_eur(data['overdue_amount'])}"
                if data["overdue_count"] else "")
        return (f"Facturas pendientes de cobro: {data['pending_count']} por {_eur(data['pending_amount'])}"
                f"{over}.{drafts}")
    if chat_action == "get_sales_performance" and "current" in data:
        cur, prev, d = data["current"], data["previous"], data["window_days"]
        if not cur["tpv_count"] and not cur["invoice_count"]:
            return f"No hay ventas registradas en tu empresa en los últimos {d} días (ni TPV ni facturas)."
        parts = []
        if cur["tpv_count"]:
            parts.append(f"{cur['tpv_count']} tickets TPV por {_eur(cur['tpv_total'])}")
        if cur["invoice_count"]:
            parts.append(f"{cur['invoice_count']} facturas por {_eur(cur['invoice_total'])}")
        if data["change_pct"] is None:
            trend = f" No hay ventas en los {d} días anteriores para comparar."
        else:
            trend = (f" Frente a los {d} días anteriores ({_eur(prev['total'])}): "
                     f"{'+' if data['change_pct'] >= 0 else ''}{data['change_pct']:g}%.")
        top = data.get("top_products") or []
        tops = (" Lo más vendido: " + ", ".join(f"{p['name']} ({_eur(p['revenue'])})" for p in top) + ".") if top else ""
        return f"Ventas de los últimos {d} días: {_eur(cur['total'])} ({' y '.join(parts)}).{trend}{tops}"
    if chat_action == "get_attendance_status" and "checkins_today" in data:
        if not data["checkins_today"] and not data["currently_in"]:
            return "Hoy no hay fichajes registrados en tu empresa."
        extra = []
        if data["late_today"]:
            extra.append(f"{data['late_today']} con entrada tarde")
        if data["with_irregularities_today"]:
            extra.append(f"{data['with_irregularities_today']} con incidencias")
        tail = f" ({', '.join(extra)})" if extra else ""
        return (f"Fichajes de hoy: {data['checkins_today']} entradas de {data['employees_today']} empleado(s); "
                f"ahora mismo dentro: {data['currently_in']}{tail}.")
    if chat_action == "get_today_agenda" and "reservations" in data:
        if not data["items"]:
            return "Hoy no tienes reservas ni reuniones en la agenda de tu empresa."
        parts = []
        for i in data["items"]:
            if i["kind"] == "reservation":
                parts.append(f"{i['time']} reserva {i['name']} ({i['guests']} pax)")
            else:
                parts.append(f"{i['time']} reunión con {i['name']}")
        head = (f"Agenda de hoy: {data['reservations']} reserva(s) ({data['guests']} comensales) y "
                f"{data['meetings']} reunión(es).")
        return f"{head} " + "; ".join(parts) + "."
    if chat_action == "review_contracts" and "pending_review" in data:
        if not data["total"]:
            return "No hay contratos guardados de tu empresa en JUSTICIA."
        states = ", ".join(f"{n} {st}" for st, n in sorted(data["by_status"].items()))
        pend = (f" {data['pending_review']} borrador(es) sin firmar pendientes de revisión."
                if data["pending_review"] else " No hay borradores pendientes de revisión.")
        return f"Contratos de tu empresa: {data['total']} ({states}); firmados: {data['signed']}.{pend}"
    if chat_action == "track_leads" and "open_leads" in data:
        if not data["open_leads"]:
            return "No tienes leads abiertos en el CRM de tu empresa."
        return (f"Leads abiertos en tu CRM: {data['open_leads']} "
                f"({data.get('high_priority', 0)} de prioridad alta, {data.get('with_meeting', 0)} con reunión).")
    if chat_action == "get_security_status" and "events_total" in data:
        if not data["events_total"]:
            return f"THALOS no tiene eventos de seguridad de tu empresa en los últimos {data['window_days']} días."
        rec = data.get("recent_denials") or []
        tail = ("" if not rec else " Últimos rechazos: "
                + ", ".join(f"{r.get('rule') or r.get('event_type')} ({r.get('severity')})" for r in rec[:3]) + ".")
        return (f"Seguridad de tu empresa ({data['window_days']} días): {data['events_total']} eventos, "
                f"{data['denied_total']} rechazados, {data['critical_total']} críticos.{tail}")
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
    src = action.payload or {}
    payload = {k: src[k] for k in READ_PAYLOAD_KEYS.get(action.action_type, ()) if src.get(k) is not None}
    try:
        out = await execute_agent_action(db, user=user, agent=agent, action=exec_name, payload=payload)
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
