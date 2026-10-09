"""
Executor unificado v2 — agentes ejecutan servicios reales (execution_over_text).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.zeus_action import ZeusAction
from services import zeus_orchestrator_handlers as orch
from services.cashflow_ledger_service import get_balance, get_summary
from services.zeus_core_metrics_v1 import get_core_metrics
from services.zeus_human_approval_v1 import request_approval, requires_approval

import services.crm_office_service as crm_svc

logger = logging.getLogger(__name__)

MANDATORY_ACTIONS = {
    "ZEUS": frozenset({"create_customer", "get_customers", "send_campaign", "get_cashflow", "get_metrics"}),
    "RAFAEL": frozenset(
        {"generate_invoice", "register_qr_payment", "generate_model_303", "get_tax_summary"}
    ),
    "PERSEO": frozenset({"create_campaign", "launch_campaign", "track_leads"}),
    # J9c. Lectura: sin aprobacion. Escritura (AFRODITA): siempre por aprobacion (CRITICAL_ACTIONS).
    "JUSTICIA": frozenset({"run_compliance_audit", "get_legal_status"}),
    "AFRODITA": frozenset(
        {"get_shift_status", "get_inventory_status", "create_ops_route", "create_inventory_movement"}
    ),
}
# Acciones nuevas (J9c) que solo valen con su agente: un cliente no puede pedir una accion de
# AFRODITA diciendo que es de otro agente (ni al reves).
_STRICT_AGENT_ACTIONS: Dict[str, str] = {
    a: ag for ag in ("JUSTICIA", "AFRODITA") for a in MANDATORY_ACTIONS[ag]
}
_STRICT_AGENT_ACTIONS["register_qr_payment"] = "RAFAEL"  # J2b
_MAX_DELIVERIES = 50


def track_leads_summary(db: Session, user: User) -> Dict[str, Any]:
    from app.models.crm_lead import CrmLead

    cid = crm_svc.primary_company_id(db, user)
    leads = db.query(CrmLead).filter(CrmLead.company_id == cid, CrmLead.status == "open").all()
    return {
        "open_leads": len(leads),
        "high_priority": sum(1 for l in leads if (l.customer_priority or "") == "high"),
        "with_meeting": sum(1 for l in leads if l.meeting_at is not None),
    }


def _fail(message: str, **extra: Any) -> Dict[str, Any]:
    return {"success": False, "executed": False, "message": message, **extra}


def _blocked_module_result(
    db: Session, user: User, agent: str, act: str, cid: Optional[int]
) -> Optional[Dict[str, Any]]:
    """J9c: control de modulos para TODAS las acciones del ejecutor. None si permitida.
    Bloqueo -> success False, status `blocked_module`, registro J7 (ACTUAR), sin ejecutar."""
    from services import module_gate
    from services.chain_log import log_chain_step

    blocked = module_gate.check_executor_action(db, user, act)
    if not blocked:
        return None
    log_chain_step(
        "ACTUAR", company_id=cid, user=user, agent=agent, action=act, status="blocked_module",
        details={"module": blocked["module"], "action_type": act, "agent": agent},
    )
    return _fail(blocked["message"], status="blocked_module", module=blocked["module"])


def _clean_afrodita_payload(db: Session, act: str, data: Dict[str, Any], cid: Optional[int]):
    """Valida y normaliza el payload de las escrituras AFRODITA (solo claves conocidas; nunca
    company_id/user_id del cliente). -> (payload_limpio, mensaje_vista_previa) o (None, error)."""
    if act == "create_ops_route":
        origin = str(data.get("origin") or "").strip()
        dest = str(data.get("destination") or "").strip()
        deliveries = data.get("deliveries") or []
        if not origin or not dest:
            return None, "origin y destination son obligatorios."
        if not isinstance(deliveries, list) or not all(isinstance(d, dict) for d in deliveries):
            return None, "deliveries debe ser una lista de objetos."
        if len(deliveries) > _MAX_DELIVERIES:
            return None, f"Maximo {_MAX_DELIVERIES} entregas por ruta."
        clean = {"origin": origin[:255], "destination": dest[:255], "deliveries": deliveries}
        return clean, f"Crear ruta operativa {clean['origin']} -> {clean['destination']} ({len(deliveries)} paradas)."

    # create_inventory_movement
    try:
        product_id = int(data.get("product_id"))
        quantity = float(data.get("quantity"))
    except (TypeError, ValueError):
        return None, "product_id (entero) y quantity (numero) son obligatorios."
    if product_id <= 0 or quantity == 0:
        return None, "product_id debe ser > 0 y quantity distinto de 0."
    from fastapi import HTTPException

    from app.models.erp import Product
    from services.afrodita_ops_service_v1 import _parse_movement_type

    try:
        mtype = _parse_movement_type(str(data.get("movement_type") or "adjustment"))
    except HTTPException as exc:
        return None, str(exc.detail)
    product = db.query(Product).filter(Product.id == product_id, Product.company_id == cid).first()
    if not product:
        return None, f"Producto {product_id} no encontrado en tu empresa."
    if not product.track_inventory:
        return None, "El producto no tiene control de inventario activo."
    after = float(product.quantity_on_hand or 0) + quantity
    if after < 0:
        return None, "Stock resultante negativo."
    clean = {
        "product_id": product_id,
        "movement_type": mtype.value,
        "quantity": quantity,
        "reference": (str(data["reference"])[:100] if data.get("reference") else None),
        "notes": (str(data["notes"])[:1000] if data.get("notes") else None),
    }
    return clean, (
        f"Movimiento {mtype.value} de {quantity:g} uds de «{product.name}» ({product.sku}): "
        f"stock {float(product.quantity_on_hand or 0):g} -> {after:g}."
    )


def _clean_qr_payment_payload(data: Dict[str, Any]):
    """J2b: lista blanca del payload de `register_qr_payment` (nunca company_id/user_id/ids del
    cliente). -> (payload_limpio, vista_previa) o (None, error)."""
    name = str(data.get("customer_name") or "").strip()
    import math
    import re

    try:
        amount = round(float(data.get("amount")), 2)
    except (TypeError, ValueError, OverflowError):
        return None, "amount (numero) es obligatorio."
    if not name:
        return None, "customer_name es obligatorio."
    if not math.isfinite(amount) or amount <= 0 or amount > 10_000_000:
        return None, "El importe debe ser un numero finito entre 0,01 y 10.000.000."
    currency = str(data.get("currency") or "EUR").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        return None, "La moneda debe ser un codigo de 3 letras (ej. EUR)."
    email = str(data.get("email") or "").strip() or None
    from pydantic import ValidationError

    from app.schemas.customer import CustomerCreate

    try:  # mismo validador que la creacion real del cliente (nombre y email)
        CustomerCreate(name=name, email=email or "scan@example.com")
    except ValidationError as exc:
        first = (exc.errors() or [{}])[0]
        return None, f"cliente no valido ({'.'.join(str(x) for x in first.get('loc', ()))}: {first.get('msg')})."
    clean = {
        "customer_name": name[:255],
        "email": email,
        "amount": amount,
        "currency": currency,
        "source": "qr_scan",
    }
    return clean, f"Registrar cobro QR de {amount:.2f} {clean['currency']} de «{clean['customer_name']}» (borrador de factura y entrada de caja)."


def _afrodita_writes_blocked() -> Optional[Dict[str, Any]]:
    from services.afrodita_unified_control import writes_enabled

    if writes_enabled():
        return None
    return _fail(
        "Escritura AFRODITA deshabilitada: configura AFRODITA_EXECUTION_ENABLED=true y "
        "AFRODITA_READ_ONLY_MODE=false.",
        status="writes_disabled",
    )


async def execute_agent_action(
    db: Session,
    *,
    user: User,
    agent: str,
    action: str,
    payload: Optional[Dict[str, Any]] = None,
    approval_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Ejecuta acción de agente. Si requiere aprobación → cola HITL (pendiente
    persistido). La unica via de saltarse la cola es `approval_id`, que SOLO
    pasa el servidor (zeus_human_approval_v1.execute_approval) tras una
    aprobacion del mismo usuario; nunca viene del cliente.
    """
    force_execute = approval_id is not None
    agent_u = (agent or "ZEUS").strip().upper()
    if agent_u == "ZEUS CORE":
        agent_u = "ZEUS"
    act = (action or "").strip().lower()
    data = dict(payload or {})

    from services.zeus_core_guard_v1 import (
        SIMULATED_HANDLER_ACTIONS,
        guard_enforce,
        validate_critical_action,
    )

    gr = validate_critical_action(
        "agents",
        act,
        target_user=user,
        company_id=crm_svc.primary_company_id(db, user) if user else None,
        actor_id=user.id if user else None,
        actor_email=user.email if user else None,
        layer="agent",
        db=db,
        payload=data,
    )
    if act in SIMULATED_HANDLER_ACTIONS:
        return {
            "success": True,
            "executed": False,
            "execution_mode": "simulated",
            "message": gr.human_message or "Acción simulada — sin mutación de BD",
            "guard": gr.to_dict(),
        }
    if not gr.allowed and guard_enforce():
        return {
            "success": False,
            "executed": False,
            "execution_mode": "blocked",
            "message": gr.human_message,
            "guard": gr.to_dict(),
        }

    cid = crm_svc.primary_company_id(db, user)

    # J9c: accion de un agente concreto pedida con otro agente -> rechazo (antes de aprobar nada).
    strict_agent = _STRICT_AGENT_ACTIONS.get(act)
    if strict_agent and agent_u != strict_agent:
        return _fail(f"La accion «{act}» pertenece a {strict_agent}, no a {agent_u}.", status="agent_mismatch")

    # J9c: control de modulos de la empresa para todas las acciones, tambien antes de pedir aprobacion.
    blocked = _blocked_module_result(db, user, agent_u, act, cid)
    if blocked:
        _log_execution(agent_u, act, user, cid, approval_id, "failed",
                       {"message": blocked["message"], "status": "blocked_module"})
        return blocked

    preview_msg: Optional[str] = None
    if act in ("create_ops_route", "create_inventory_movement") and not force_execute:
        wb = _afrodita_writes_blocked()
        if wb:
            return wb
        data, preview_msg = _clean_afrodita_payload(db, act, data, cid)
        if data is None:
            return _fail(preview_msg, status="invalid_payload")

    if act == "register_qr_payment" and not force_execute:
        data, preview_msg = _clean_qr_payment_payload(data)
        if data is None:
            return _fail(preview_msg, status="invalid_payload")

    if act == "create_customer" and not force_execute:
        # J12b: mismo validador que la ejecucion, ANTES de abrir aprobacion (la ejecucion lo repite).
        from pydantic import ValidationError
        from app.schemas.customer import CustomerCreate

        name = str(data.get("name") or "").strip()
        email = str(data.get("email") or "").strip()
        if not name or not email:
            return _fail("Indica nombre y email del cliente (ej: crear cliente Juan juan@empresa.com).",
                         status="invalid_payload")
        try:
            CustomerCreate(name=name, email=email, phone=data.get("phone"))
        except ValidationError as exc:
            first = (exc.errors() or [{}])[0]
            field = ".".join(str(x) for x in first.get("loc", ())) or "datos"
            return _fail(
                f"No se creó el cliente: {field} no es válido ({first.get('msg', 'valor incorrecto')}).",
                status="invalid_payload",
            )

    if requires_approval(act, data) and not force_execute:
        approval = request_approval(
            db,
            user=user,
            company_id=cid,
            agent_name=agent_u,
            action_type=act,
            payload=data,
        )
        return {
            "success": True,
            "executed": False,
            "needs_approval": True,
            "approval_id": approval.id,
            "message": f"Acción «{act}» pendiente de aprobación humana (ID {approval.id})."
            + (f" Vista previa: {preview_msg}" if preview_msg else ""),
            **({"preview": preview_msg} if preview_msg else {}),
        }

    zeus_action = ZeusAction(
        action_type=_map_action_to_zeus_type(act),
        company_id=cid,
        user_id=user.id,
        payload=data,
        requires_confirmation=act in ("send_campaign", "launch_campaign") and not force_execute,
    )

    try:
        result = await _dispatch(db, user, agent_u, act, zeus_action, data, force_execute=force_execute)
    except Exception as exc:
        _log_execution(agent_u, act, user, cid, approval_id, "failed", {"error": str(exc)})
        raise
    ok = bool(result.get("success")) and bool(result.get("executed"))
    _log_execution(
        agent_u, act, user, cid, approval_id,
        "completed" if ok else "failed",
        {"message": result.get("message"), "executed": result.get("executed")},
    )
    return result


def _log_execution(
    agent: str, action: str, user: User, company_id: Optional[int],
    approval_id: Optional[int], st: str, extra: Dict[str, Any],
) -> None:
    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name=agent,
            action_type=f"agent_action_{action}",
            action_description=f"Ejecucion de {action} por {agent}"
            + (f" (aprobacion {approval_id})" if approval_id else ""),
            details={"action": action, "approval_id": approval_id, **extra},
            user_email=getattr(user, "email", None),
            status=st,
            company_id=company_id,
        )
    except Exception:
        logger.exception("No se pudo registrar la ejecucion de %s", action)


def _map_action_to_zeus_type(action: str) -> str:
    mapping = {
        "get_customers": "list_customers",
        "get_metrics": "get_metrics",
        "get_cashflow": "get_cashflow",
        "send_campaign": "send_campaign",
        "launch_campaign": "send_campaign",
        "create_campaign": "send_campaign",
        "create_customer": "create_customer",
        "generate_invoice": "generate_invoice",
        "generate_model_303": "generate_model_303",
        "get_tax_summary": "get_tax_summary",
        "track_leads": "track_leads",
        # J9c: acciones propias del ejecutor; ZeusActionType (orquestador/chat) no las contempla.
        "get_shift_status": "shift_status",
        "run_compliance_audit": "unknown",
        "get_legal_status": "unknown",
        "get_inventory_status": "unknown",
        "create_ops_route": "unknown",
        "create_inventory_movement": "unknown",
        "register_qr_payment": "unknown",
    }
    return mapping.get(action, action)


async def _dispatch(
    db: Session,
    user: User,
    agent: str,
    action: str,
    zeus_action: ZeusAction,
    payload: Dict[str, Any],
    *,
    force_execute: bool,
) -> Dict[str, Any]:
    from services.zeus_orchestrator_service import execute_action

    # J9c: modulo activo de la empresa para TODA accion (tambien las ejecutadas tras una aprobacion,
    # por si el modulo se desactivo entre la solicitud y la confirmacion).
    blocked = _blocked_module_result(db, user, agent, action, zeus_action.company_id)
    if blocked:
        return blocked

    # ZEUS
    if action == "create_customer":
        # Misma logica que el chat: execute_create_customer (valida email, errores controlados).
        r = await execute_action(db, user, zeus_action, force_execute=force_execute)
        return r.model_dump()

    if action in ("get_customers", "list_customers"):
        r = orch.execute_list_customers(db, user, zeus_action)
        return r.model_dump()

    if action in ("send_campaign", "launch_campaign", "create_campaign"):
        r = await execute_action(db, user, zeus_action, force_execute=force_execute)
        return r.model_dump()

    if action == "get_cashflow":
        cid = crm_svc.primary_company_id(db, user)
        bal = get_balance(db, company_id=cid)
        summary = get_summary(db, company_id=cid, days=int(payload.get("days") or 30))
        return {
            "success": True,
            "executed": True,
            "message": f"Cashflow balance: {bal:.2f} €",
            "data": {"balance": bal, "summary": summary},
        }

    if action == "get_metrics":
        metrics = get_core_metrics(db, user=user, days=int(payload.get("days") or 30))
        return {
            "success": True,
            "executed": True,
            "message": (
                f"Métricas: revenue {metrics['revenue']}€, staff_cost {metrics['staff_cost']}€, "
                f"product_cost {metrics['product_cost']}€"
            ),
            "data": metrics,
        }

    # RAFAEL
    if action == "generate_invoice":
        invoice_id = payload.get("invoice_id")
        if not invoice_id:
            return {"success": False, "executed": False, "message": "invoice_id requerido."}
        from services.rafael_fiscal_engine_v2 import generate_invoice_pdf_flow

        out = generate_invoice_pdf_flow(db, user=user, invoice_id=int(invoice_id))
        return {"success": True, "executed": True, "message": "Factura PDF generada.", "data": out}

    if action == "register_qr_payment":
        return _execute_register_qr_payment(db, user, zeus_action, payload)

    if action == "generate_model_303":
        year = int(payload.get("year") or 2026)
        quarter = int(payload.get("quarter") or 1)
        from services.rafael_fiscal_engine_v2 import generate_model_303_flow

        out = generate_model_303_flow(
            db, user=user, company_id=crm_svc.primary_company_id(db, user), year=year, quarter=quarter
        )
        return {"success": True, "executed": True, "message": "Modelo 303 generado.", "data": out}

    if action == "get_tax_summary":
        from services.rafael_fiscal_engine_v2 import fetch_period_financials

        cid = crm_svc.primary_company_id(db, user)
        year = int(payload.get("year") or 2026)
        quarter = int(payload.get("quarter") or 1)
        fin = fetch_period_financials(db, company_id=cid, year=year, quarter=quarter)
        return {"success": True, "executed": True, "message": "Resumen fiscal del periodo.", "data": fin}

    # PERSEO
    if action == "track_leads":
        data = track_leads_summary(db, user)
        return {"success": True, "executed": True, "message": f"Leads abiertos: {data['open_leads']}", "data": data}

    if action == "create_campaign":
        preview = orch.preview_send_campaign(db, user, zeus_action)
        return {"success": True, "executed": True, "message": preview.get("message"), "data": preview}

    # JUSTICIA (lectura; servicios reales de justice_audit_service, ambito del usuario de la sesion)
    if action in ("run_compliance_audit", "get_legal_status"):
        from services import justice_audit_service as justice

        if action == "get_legal_status":
            body = justice.audit_status(db, user)
            return {
                "success": True, "executed": True, "company_id": zeus_action.company_id,
                "message": f"Documentos legales: {body['legal_documents']}.", "data": body,
            }
        audit = justice.run_real_audit(db, user)
        if not audit.get("real_execution"):
            return _fail(f"Auditoria JUSTICIA no disponible: {audit.get('error', 'desactivada')}")
        db.commit()  # run_real_audit sincroniza eventos de cumplimiento (como GET /justice/audit)
        return {
            "success": True, "executed": True, "company_id": zeus_action.company_id,
            "message": "Auditoria de cumplimiento ejecutada.", "data": audit,
        }

    # AFRODITA
    if action == "get_shift_status":
        r = orch.execute_shift_status(db, user, zeus_action)
        return r.model_dump()

    if action == "get_inventory_status":
        from fastapi import HTTPException

        from services.afrodita_ops_service_v1 import company_inventory_status

        cid = zeus_action.company_id
        if cid is None:
            return _fail("El usuario no tiene empresa asociada.")
        try:
            inv = company_inventory_status(db, cid)
        except HTTPException as exc:
            return _fail(str(exc.detail))
        return {
            "success": True, "executed": True, "company_id": cid,
            "message": f"Inventario: {inv['total_skus']} referencias, {inv['low_stock_count']} con stock bajo.",
            "data": inv,
        }

    if action in ("create_ops_route", "create_inventory_movement"):
        from fastapi import HTTPException

        from services import afrodita_ops_service_v1 as afro

        cid = zeus_action.company_id
        wb = _afrodita_writes_blocked()
        if wb:
            return wb
        if cid is None:
            return _fail("El usuario no tiene empresa asociada.")
        try:
            if action == "create_ops_route":
                out = afro.create_ops_route(
                    db, user,
                    origin=str(payload.get("origin") or ""),
                    destination=str(payload.get("destination") or ""),
                    deliveries=payload.get("deliveries") or [],
                )
            else:
                out = afro.create_inventory_movement(
                    db, user,
                    product_id=int(payload.get("product_id") or 0),
                    movement_type=str(payload.get("movement_type") or "adjustment"),
                    quantity=float(payload.get("quantity") or 0),
                    reference=payload.get("reference"),
                    notes=payload.get("notes"),
                    company_id=cid,
                )
            db.commit()
        except HTTPException as exc:
            db.rollback()
            return _fail(str(exc.detail))
        return {
            "success": True, "executed": True, "company_id": cid,
            "message": out.get("message") or "Accion AFRODITA ejecutada.", "data": out,
        }

    r = await execute_action(db, user, zeus_action, force_execute=force_execute)
    out = r.model_dump()
    out["executed"] = r.executed
    return out


def _execute_register_qr_payment(
    db: Session, user: User, zeus_action: ZeusAction, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """J2b: ejecuta el cobro QR aprobado: cliente (buscar/crear en la empresa del servidor),
    borrador de factura (NO emitida) y entrada de caja, con la misma logica que la rama <500."""
    from fastapi import HTTPException

    from services.scan_flow_service_v1 import _find_or_create_customer, apply_qr_payment_effects

    cid = zeus_action.company_id
    if cid is None:
        return _fail("El usuario no tiene empresa asociada.")
    clean, err = _clean_qr_payment_payload(dict(payload or {}))
    if clean is None:
        return _fail(err, status="invalid_payload")
    try:
        cust, created = _find_or_create_customer(
            db, user, company_id=cid, name=clean["customer_name"], email=clean["email"]
        )
        invoice_id = apply_qr_payment_effects(
            db, user, company_id=cid, customer=cust, amount=clean["amount"],
            customer_name=clean["customer_name"],
        )
        db.commit()
        from app.models.cashflow_ledger import CashflowLedgerEntry

        ledger = (
            db.query(CashflowLedgerEntry)
            .filter(CashflowLedgerEntry.company_id == cid, CashflowLedgerEntry.invoice_id == invoice_id)
            .count()
        )
    except HTTPException as exc:
        db.rollback()
        return _fail(str(exc.detail))
    if not ledger:
        # Factura creada pero la caja no se registro (guard/integridad): no se declara exito.
        return _fail(
            f"Se creo el borrador de factura {invoice_id} pero no se pudo registrar la entrada de caja; "
            "revisalo manualmente.",
            status="cashflow_not_recorded", invoice_id=invoice_id,
        )
    return {
        "success": True, "executed": True, "company_id": cid,
        "message": f"Cobro QR registrado: factura borrador {invoice_id} y entrada de caja de {clean['amount']:.2f} EUR.",
        "data": {"customer_id": cust.id, "customer_created": created, "invoice_id": invoice_id,
                 "amount": clean["amount"], "invoice_status": "draft", "cashflow_updated": True},
    }
