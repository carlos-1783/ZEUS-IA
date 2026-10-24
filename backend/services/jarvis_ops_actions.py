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
    "get_last_invoice": ("get_last_invoice", "RAFAEL"),
    "get_invoices_today": ("get_invoices_today", "RAFAEL"),
    "get_invoices_period": ("get_invoices_period", "RAFAEL"),
    "get_vat_quarter": ("get_vat_quarter", "RAFAEL"),
    "get_sales_performance": ("get_sales_performance", "PERSEO"),
    "get_attendance_status": ("get_attendance_status", "AFRODITA"),
    "get_today_agenda": ("get_today_agenda", "AFRODITA"),
    "get_weekly_orders": ("get_weekly_orders", "AFRODITA"),
    "get_staff_schedule": ("get_staff_schedule", "AFRODITA"),
    "review_contracts": ("review_contracts", "JUSTICIA"),
    "get_coordination_report": ("get_coordination_report", "ZEUS"),
}
# Claves del payload del chat que cada consulta puede pasar al ejecutor (lista blanca; el resto
# del payload del chat, contexto incluido, nunca llega al ejecutor).
READ_PAYLOAD_KEYS: Dict[str, Tuple[str, ...]] = {
    "get_daily_close": ("day",),
    "get_sales_performance": ("days",),
    "get_vat_quarter": ("quarter_ref", "quarter", "year"),
    "get_staff_schedule": ("day", "week", "employee"),
    "get_invoices_period": ("period",),  # yesterday/week/last_week/month/last_month: fechas en servidor
    # alerta de stock: out/low/alerts; "product" + nombre = stock de UN producto (sin foco: resumen del inventario)
    "get_inventory_status": ("focus", "product"),
}
# Lecturas de OTRO agente que se atienden en el chat de un agente (workspace -> lecturas), con «Esto lo lleva
# <dueño>: …», por el mismo camino que en el chat de ZEUS (modulo de la empresa y ejecutor del agente dueño):
# inventario en el chat de RAFAEL y facturas/cierre en el de AFRODITA (los dos chats del dia a dia del negocio).
# El resto de workspaces (PERSEO, JUSTICIA, THALOS) siguen como antes: tests existentes fijan ese diseño.
CROSS_AGENT_READS: Dict[str, frozenset] = {
    "RAFAEL": frozenset({"get_inventory_status"}),
    "AFRODITA": frozenset({"get_last_invoice", "get_invoices_today", "get_invoices_period", "get_pending_invoices",
                           "get_daily_close"}),
}
# Consultas que, en el chat de UN agente concreto, se resuelven con otra lectura de ese agente:
# (agente, intencion del parser) -> (accion de READ_ACTIONS, payload fijo). En el workspace de RAFAEL
# «¿cuánto llevo hoy?» / «¿cuánto he facturado hoy?» (ventas TPV de hoy, que en ZEUS atiende
# tpv_sales_summary) es el cierre de hoy de RAFAEL: ventas TPV del dia + arqueo si lo hay.
AGENT_INTENT_ALIASES: Dict[Tuple[str, str], Tuple[str, Dict[str, Any]]] = {
    ("RAFAEL", "tpv_sales_today"): ("get_daily_close", {"day": "today"}),
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


_INVOICE_STATUS_ES = {"draft": "borrador sin emitir", "sent": "emitida", "paid": "cobrada",
                      "partially_paid": "cobrada en parte", "void": "anulada", "overdue": "vencida"}


def _eur(v: Any) -> str:
    return f"{float(v or 0):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _dmy(iso: Any) -> str:
    """AAAA-MM-DD -> dd/mm/aaaa (dia ya resuelto en el servidor)."""
    y, m, d = str(iso).split("-")
    return f"{d}/{m}/{y}"


def invoices_period_text(data: Dict[str, Any]) -> str:
    """Texto es-ES de `rafael_daily_reads_v1.invoices_period_summary` (mismo criterio que «facturas de hoy»:
    las emitidas suman; borradores y anuladas se cuentan aparte)."""
    label = data["period_label"]
    rango = (_dmy(data["date_from"]) if data["date_from"] == data["date_to"]
             else f"{_dmy(data['date_from'])} - {_dmy(data['date_to'])}")
    extra = []
    if data["drafts_count"]:
        extra.append(f"{data['drafts_count']} borrador(es) sin emitir")
    if data["void_count"]:
        extra.append(f"{data['void_count']} anulada(s)")
    tail = f" Además: {', '.join(extra)}." if extra else ""
    if not data["count"]:
        return (f"{label[0].upper()}{label[1:]} ({rango}) no hay facturas emitidas en tu empresa: 0 facturas."
                f"{tail}")
    listed = [i for i in data["invoices"] if i.get("status") not in ("draft", "void")]
    nums = ", ".join(f"{i['invoice_number']} ({_eur(i['amount_total'])})" for i in listed)
    more = f" y {data['count'] - len(listed)} más" if data["count"] > len(listed) else ""
    de = "del " + label[3:] if label.startswith("el ") else "de " + label
    return (f"Facturas {de} ({rango}): {data['count']} por {_eur(data['amount_total'])} "
            f"(IVA {_eur(data['tax_total'])}): {nums}{more}.{tail}")


def _format_read(chat_action: str, result: Dict[str, Any]) -> str:
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    if chat_action == "get_legal_status" and "legal_documents" in data:
        pend = data.get("pending")
        extra = f" Pendientes de revisión: {len(pend)} grupos." if isinstance(pend, (list, dict)) and pend else ""
        return (f"Estado legal de tu cuenta: {data['legal_documents']} documentos legales y "
                f"{data.get('compliance_events', 0)} eventos de cumplimiento registrados.{extra}")
    if chat_action == "get_daily_close" and "tickets" in data:
        closures = data.get("cash_closures") or []
        if closures:
            diff = sum(c["difference"] for c in closures)
            cash_txt = (f"Arqueo de caja: {len(closures)} cierre(s), efectivo contado "
                        f"{_eur(sum(c['counted_cash'] for c in closures))}, descuadre {_eur(diff)}.")
        else:
            cash_txt = data.get("note") or ""
        if not data["tickets"]:
            return f"No hay ventas TPV registradas el {data['date']} en tu empresa. {cash_txt}".strip()
        methods = ", ".join(f"{m} {_eur(v['total'])} ({v['count']})" for m, v in data["by_payment_method"].items())
        return (f"Cierre del {data['date']}: {data['tickets']} tickets, total {_eur(data['total'])} "
                f"(IVA {_eur(data['tax_total'])}, ticket medio {_eur(data['average_ticket'])}). "
                f"Por forma de pago: {methods}. {cash_txt}").strip()
    if chat_action == "get_pending_invoices" and "pending_count" in data:
        drafts = f" Además tienes {data['drafts_count']} borrador(es) sin emitir." if data["drafts_count"] else ""
        if not data["pending_count"]:
            return f"No tienes facturas pendientes de cobro.{drafts}"
        over = (f", {data['overdue_count']} vencida(s) por {_eur(data['overdue_amount'])}"
                if data["overdue_count"] else "")
        return (f"Facturas pendientes de cobro: {data['pending_count']} por {_eur(data['pending_amount'])}"
                f"{over}.{drafts}")
    if chat_action == "get_last_invoice" and "found" in data:
        if not data["found"]:
            return "No hay facturas todavía en tu empresa."
        inv = data["invoice"]
        who = f" a {inv['customer']}" if inv.get("customer") else ""
        state = _INVOICE_STATUS_ES.get(inv.get("status") or "", inv.get("status") or "sin estado")
        due = f", pendiente de cobro {_eur(inv['amount_due'])}" if inv["amount_due"] and inv.get("status") != "void" else ""
        origin = " Generada desde una venta del TPV." if inv.get("from_tpv") else ""
        return (f"Última factura: {inv['invoice_number']} del {inv['issue_date'] or 'sin fecha'}{who}, total "
                f"{_eur(inv['amount_total'])} (IVA {_eur(inv['tax_amount'])}), {state}{due}.{origin}")
    if chat_action == "get_invoices_today" and "invoices" in data:
        extra = []
        if data["drafts_count"]:
            extra.append(f"{data['drafts_count']} borrador(es) sin emitir")
        if data["void_count"]:
            extra.append(f"{data['void_count']} anulada(s)")
        tail = f" Además: {', '.join(extra)}." if extra else ""
        if not data["count"]:
            return f"Hoy ({_dmy(data['date'])}) no hay facturas emitidas en tu empresa: 0 facturas.{tail}"
        nums = ", ".join(f"{i['invoice_number']} ({_eur(i['amount_total'])})" for i in data["invoices"]
                         if i.get("status") not in ("draft", "void"))
        return (f"Facturas de hoy ({_dmy(data['date'])}): {data['count']} por {_eur(data['amount_total'])} "
                f"(IVA {_eur(data['tax_total'])}): {nums}.{tail}")
    if chat_action == "get_invoices_period" and "period_label" in data:
        return invoices_period_text(data)
    if chat_action == "get_vat_quarter" and "vat_total" in data:
        q = f"{data['quarter']}T {data['year']}"
        if not data["sales_count"]:
            return f"No hay ventas TPV registradas en el {q}: IVA repercutido 0,00 €. {data['note']}"
        parts = [f"{r['rate']} base {_eur(r['tax_base'])} cuota {_eur(r['vat_amount'])}"
                 for r in data["by_rate"] if r["tax_base"] or r["vat_amount"]]
        rec = f" Recargo de equivalencia {_eur(data['recargo_total'])}." if data["recargo_total"] else ""
        return (f"IVA repercutido en las ventas TPV del {q}: {_eur(data['vat_total'])} sobre una base de "
                f"{_eur(data['base_total'])} ({data['sales_count']} {'venta' if data['sales_count'] == 1 else 'ventas'}, total {_eur(data['grand_total'])}). "
                f"Por tipo: {'; '.join(parts)}.{rec} {data['note']}")
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
        return (f"Contratos de tu empresa: {data['total']} ({states}); con sello de integridad (hash, "
                f"no es firma eIDAS): {data['integrity_sealed']}.{pend}")
    if chat_action == "get_coordination_report" and "activities_by_agent" in data:
        d = data["window_days"]
        if not data["activities_total"]:
            head = f"No hay actividad de los agentes de tu empresa en los últimos {d} días."
        else:
            agents = ", ".join(f"{a} {sum(st.values())}" for a, st in data["activities_by_agent"].items())
            head = f"Coordinación ({d} días): {data['activities_total']} actividades ({agents})."
        probs = data.get("problems") or []
        ptxt = (f" {len(probs)} fallida(s)/bloqueada(s), la última: {probs[0]['agent']} {probs[0]['action_type']} "
                f"({probs[0]['status']}).") if probs else " Ninguna fallida ni bloqueada."
        pend = data.get("pending_approvals") or {}
        atxt = (" Aprobaciones pendientes: " + ", ".join(f"{a} {n}" for a, n in pend.items()) + "."
                if pend else " Sin aprobaciones pendientes.")
        return head + ptxt + atxt
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
        from services.afrodita_ops_service_v1 import inventory_alerts_text, inventory_status_text, product_stock_text

        # alerta de stock pedida («productos sin stock», «¿algo bajo mínimos?») o UN producto: solo lo preguntado
        if data.get("focus") == "product":
            return product_stock_text(data, data.get("product") or "")
        return inventory_alerts_text(data, data["focus"]) if data.get("focus") else inventory_status_text(data)
    if chat_action == "get_staff_schedule" and "employees_total" in data:
        from services.afrodita_workspace_service_v1 import staff_schedule_text

        return staff_schedule_text(data)
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
        return ZeusExecutionResult(success=False, intent=action.action_type, message=str(exc.detail), executed=False,
                                   status="error")
    except Exception:
        db.rollback()
        logger.exception("jarvis_ops: fallo ejecutando %s", exec_name)
        return ZeusExecutionResult(
            success=False, intent=action.action_type, executed=False,
            message="No se pudo completar la consulta; inténtalo de nuevo.", status="error",
        )
    ok = bool(out.get("success")) and bool(out.get("executed"))
    return ZeusExecutionResult(
        success=ok, intent=action.action_type, executed=ok,
        message=_format_read(action.action_type, out) if ok else str(out.get("message") or "No se pudo completar la consulta."),
        metrics=out.get("data") if isinstance(out.get("data"), dict) else {},
        company_id=out.get("company_id"),
        status=None if ok else str(
            out.get("status") or ("blocked_guard" if out.get("execution_mode") == "blocked" else "failed")
        ),
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
