"""Registro fiscal obligatorio de ventas (TPV y CMR) en RAFAEL."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_rafael_instance: Optional[Any] = None


class RafaelFiscalError(Exception):
    """Error al registrar venta/cobro en RAFAEL; no debe confirmarse la operación."""


def get_rafael_agent():
    """Instancia RAFAEL (lazy); no depende de que el chat haya inicializado agentes."""
    global _rafael_instance
    if _rafael_instance is None:
        from agents.rafael import Rafael

        _rafael_instance = Rafael()
        logger.info("RAFAEL agent loaded for fiscal persistence")
    return _rafael_instance


def build_cmr_fiscal_ticket(
    *,
    ticket_id: str,
    service_name: str,
    cart_line: Dict[str, Any],
    fiscal_items: List[Dict[str, Any]],
    payment_method: str,
    company_id: int,
    customer_id: int,
    customer_name: Optional[str] = None,
    record_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Mapea cobro CMR oficina al formato fiscal unificado (mismo motor que TPV)."""
    subtotal = float(sum(Decimal(str(i["base_amount"])) for i in fiscal_items))
    tax = float(sum(Decimal(str(i["tax_amount"])) for i in fiscal_items))
    total = subtotal + tax
    line_name = (service_name or cart_line.get("name") or "Servicio").strip()[:200]
    item = {
        "product_id": str(cart_line.get("product_id") or "CRM_OFFICE"),
        "name": line_name,
        "quantity": float(cart_line.get("quantity") or 1),
        "price": float(cart_line.get("price") or subtotal),
        "iva_rate": float(cart_line.get("iva_rate") or 21),
        "subtotal": subtotal,
        "subtotal_with_iva": total,
        "category": "servicios",
    }
    return {
        "id": ticket_id,
        "type": "service_sale",
        "source": "CMR",
        "date": datetime.now(timezone.utc).isoformat(),
        "items": [item],
        "totals": {
            "subtotal": subtotal,
            "iva": tax,
            "total": total,
            "items_count": 1,
        },
        "payment_method": payment_method,
        "business_profile": "office",
        "company_id": company_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "service_name": line_name,
        "crm_record_id": record_id,
    }


def persist_sale(
    *,
    db: Any,
    user_id: int,
    company_id: Optional[int],
    ticket: Dict[str, Any],
    tpv_sale_id: int,
    user_email: Optional[str] = None,
    source: str = "TPV",
) -> Dict[str, Any]:
    """
    Registra venta/cobro en RAFAEL. Obligatorio tras persist_fiscal_sale (flush).
    Lanza RafaelFiscalError si falla.
    """
    ticket_id = ticket.get("id")
    totals = ticket.get("totals") or {}
    payload = {
        "company_id": company_id,
        "sale_id": tpv_sale_id,
        "ticket_id": ticket_id,
        "items": ticket.get("items") or [],
        "total_amount": totals.get("total"),
        "taxes": totals.get("iva"),
        "payment_method": ticket.get("payment_method"),
        "timestamp": ticket.get("date"),
        "source": source,
        "type": ticket.get("type"),
        "customer_id": ticket.get("customer_id"),
        "service_name": ticket.get("service_name"),
    }
    logger.info(
        "%s → RAFAEL: enviando cobro/venta ticket_id=%s sale_id=%s company_id=%s total=%s",
        source,
        ticket_id,
        tpv_sale_id,
        company_id,
        payload["total_amount"],
    )

    rafael = get_rafael_agent()
    enriched_ticket = {
        **ticket,
        "fiscal_snapshot_id": tpv_sale_id,
        "company_id": company_id,
        "source": source,
    }

    if not hasattr(rafael, "process_tpv_ticket"):
        raise RafaelFiscalError("RAFAEL no expone process_tpv_ticket")

    result = rafael.process_tpv_ticket(enriched_ticket)
    if not result.get("success"):
        err = result.get("error") or "RAFAEL rechazó el registro fiscal"
        logger.error(
            "%s → RAFAEL: error ticket_id=%s sale_id=%s detail=%s",
            source,
            ticket_id,
            tpv_sale_id,
            err,
        )
        raise RafaelFiscalError(err)

    logger.info(
        "%s → RAFAEL: respuesta ok ticket_id=%s sale_id=%s draft=%s",
        source,
        ticket_id,
        tpv_sale_id,
        result.get("draft_only", True),
    )

    fiscal_doc_id = _persist_fiscal_document(db, user_id, enriched_ticket, result, source=source)
    if fiscal_doc_id:
        result["fiscal_document_id"] = fiscal_doc_id
        result["fiscal_document_persisted"] = True

    action_type = "payment_created" if source == "CMR" else "sale_created"
    _log_fiscal_event(
        user_id=user_id,
        user_email=user_email,
        company_id=company_id,
        ticket_id=ticket_id,
        tpv_sale_id=tpv_sale_id,
        payload=payload,
        rafael_result=result,
        source=source,
        action_type=action_type,
    )
    return result


def _persist_fiscal_document(
    db: Any,
    user_id: int,
    ticket: Dict[str, Any],
    rafael_result: Dict[str, Any],
    *,
    source: str = "TPV",
) -> Optional[int]:
    try:
        from services.legal_fiscal_firewall import firewall

        firewall.db = db
        fiscal_content = {
            "ticket_id": ticket.get("id"),
            "sale_id": ticket.get("fiscal_snapshot_id"),
            "company_id": ticket.get("company_id"),
            "source": source,
            "fiscal_data": rafael_result.get("fiscal_data", {}),
            "accounting_entry": rafael_result.get("accounting_entry", {}),
            "libro_ingresos": rafael_result.get("libro_ingresos", {}),
            "resumen_diario": rafael_result.get("resumen_diario", {}),
            "resumen_mensual": rafael_result.get("resumen_mensual", {}),
            "model_303_ready": rafael_result.get("model_303_ready", False),
            "draft_only": rafael_result.get("draft_only", True),
            "legal_disclaimer": rafael_result.get(
                "legal_disclaimer",
                "ZEUS no presenta impuestos automáticamente",
            ),
        }
        doc_type = (
            f"cmr_{ticket.get('type', 'service_sale')}"
            if source == "CMR"
            else f"tpv_{ticket.get('type', 'ticket')}"
        )
        fiscal_doc = firewall.generate_draft_document(
            agent_name="RAFAEL",
            user_id=user_id,
            document_type=doc_type,
            content=fiscal_content,
            metadata={
                "ticket_id": ticket.get("id"),
                "sale_id": ticket.get("fiscal_snapshot_id"),
                "source": source,
                "business_profile": ticket.get("business_profile"),
                "payment_method": ticket.get("payment_method"),
                "total": ticket.get("totals", {}).get("total", 0),
                "customer_id": ticket.get("customer_id"),
                "service_name": ticket.get("service_name"),
            },
        )
        doc_id = fiscal_doc.get("document_id")
        if doc_id and db:
            from app.models.document_approval import DocumentApproval

            doc_approval = db.query(DocumentApproval).filter(DocumentApproval.id == doc_id).first()
            if doc_approval:
                doc_approval.ticket_id = ticket.get("id")
                doc_approval.fiscal_document_type = doc_type
                audit_log = list(doc_approval.audit_log or [])
                audit_log.append(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "event": "ticket_processed",
                        "ticket_id": ticket.get("id"),
                        "sale_id": ticket.get("fiscal_snapshot_id"),
                        "source": source,
                        "fiscal_document_generated": True,
                    }
                )
                doc_approval.audit_log = audit_log
        return int(doc_id) if doc_id else None
    except Exception as exc:
        logger.exception(
            "%s → RAFAEL: fallo persistiendo documento fiscal ticket_id=%s",
            source,
            ticket.get("id"),
        )
        raise RafaelFiscalError(f"No se pudo persistir documento fiscal RAFAEL: {exc}") from exc


def _log_fiscal_event(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: Optional[int],
    ticket_id: Optional[str],
    tpv_sale_id: int,
    payload: Dict[str, Any],
    rafael_result: Dict[str, Any],
    source: str,
    action_type: str,
) -> None:
    try:
        from services.activity_logger import ActivityLogger

        label = "Cobro CMR" if source == "CMR" else "Venta TPV"
        ActivityLogger.log_activity(
            agent_name="RAFAEL",
            action_type=action_type,
            action_description=f"{label} registrado en RAFAEL: {ticket_id}",
            details={
                "ticket_id": ticket_id,
                "sale_id": tpv_sale_id,
                "company_id": company_id,
                "user_id": user_id,
                "payment_method": payload.get("payment_method"),
                "source": source,
                "customer_id": payload.get("customer_id"),
                "service_name": payload.get("service_name"),
                "fiscal_document_id": rafael_result.get("fiscal_document_id"),
            },
            metrics={
                "total_amount": payload.get("total_amount"),
                "taxes": payload.get("taxes"),
            },
            user_email=user_email,
            status="completed",
            priority="high",
            visible_to_client=True,
        )
    except Exception:
        logger.exception("Activity log %s failed ticket_id=%s", action_type, ticket_id)
