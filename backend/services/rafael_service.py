"""Registro fiscal obligatorio de ventas TPV en RAFAEL (sin fallos silenciosos)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_rafael_instance: Optional[Any] = None


class RafaelFiscalError(Exception):
    """Error al registrar venta en RAFAEL; la venta TPV no debe confirmarse."""


def get_rafael_agent():
    """Instancia RAFAEL (lazy); no depende de que el chat haya inicializado agentes."""
    global _rafael_instance
    if _rafael_instance is None:
        from agents.rafael import Rafael

        _rafael_instance = Rafael()
        logger.info("RAFAEL agent loaded for TPV fiscal persistence")
    return _rafael_instance


def persist_sale(
    *,
    db: Any,
    user_id: int,
    company_id: Optional[int],
    ticket: Dict[str, Any],
    tpv_sale_id: int,
    user_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Registra venta en RAFAEL. Obligatorio tras persist_fiscal_sale (flush).
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
    }
    logger.info(
        "TPV → RAFAEL: enviando venta ticket_id=%s sale_id=%s company_id=%s total=%s",
        ticket_id,
        tpv_sale_id,
        company_id,
        payload["total_amount"],
    )

    rafael = get_rafael_agent()
    enriched_ticket = {**ticket, "fiscal_snapshot_id": tpv_sale_id, "company_id": company_id}

    if not hasattr(rafael, "process_tpv_ticket"):
        raise RafaelFiscalError("RAFAEL no expone process_tpv_ticket")

    result = rafael.process_tpv_ticket(enriched_ticket)
    if not result.get("success"):
        err = result.get("error") or "RAFAEL rechazó la venta"
        logger.error(
            "TPV → RAFAEL: error ticket_id=%s sale_id=%s detail=%s",
            ticket_id,
            tpv_sale_id,
            err,
        )
        raise RafaelFiscalError(err)

    logger.info(
        "TPV → RAFAEL: respuesta ok ticket_id=%s sale_id=%s draft=%s",
        ticket_id,
        tpv_sale_id,
        result.get("draft_only", True),
    )

    fiscal_doc_id = _persist_fiscal_document(db, user_id, enriched_ticket, result)
    if fiscal_doc_id:
        result["fiscal_document_id"] = fiscal_doc_id
        result["fiscal_document_persisted"] = True

    _log_sale_created(
        user_id=user_id,
        user_email=user_email,
        company_id=company_id,
        ticket_id=ticket_id,
        tpv_sale_id=tpv_sale_id,
        payload=payload,
        rafael_result=result,
    )
    return result


def _persist_fiscal_document(
    db: Any,
    user_id: int,
    ticket: Dict[str, Any],
    rafael_result: Dict[str, Any],
) -> Optional[int]:
    try:
        from services.legal_fiscal_firewall import firewall

        firewall.db = db
        fiscal_content = {
            "ticket_id": ticket.get("id"),
            "sale_id": ticket.get("fiscal_snapshot_id"),
            "company_id": ticket.get("company_id"),
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
        fiscal_doc = firewall.generate_draft_document(
            agent_name="RAFAEL",
            user_id=user_id,
            document_type=f"tpv_{ticket.get('type', 'ticket')}",
            content=fiscal_content,
            metadata={
                "ticket_id": ticket.get("id"),
                "sale_id": ticket.get("fiscal_snapshot_id"),
                "business_profile": ticket.get("business_profile"),
                "payment_method": ticket.get("payment_method"),
                "total": ticket.get("totals", {}).get("total", 0),
            },
        )
        doc_id = fiscal_doc.get("document_id")
        if doc_id and db:
            from app.models.document_approval import DocumentApproval

            doc_approval = db.query(DocumentApproval).filter(DocumentApproval.id == doc_id).first()
            if doc_approval:
                doc_approval.ticket_id = ticket.get("id")
                doc_approval.fiscal_document_type = f"tpv_{ticket.get('type', 'ticket')}"
                audit_log = list(doc_approval.audit_log or [])
                audit_log.append(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "event": "ticket_processed",
                        "ticket_id": ticket.get("id"),
                        "sale_id": ticket.get("fiscal_snapshot_id"),
                        "fiscal_document_generated": True,
                    }
                )
                doc_approval.audit_log = audit_log
        return int(doc_id) if doc_id else None
    except Exception as exc:
        logger.exception(
            "TPV → RAFAEL: fallo persistiendo documento fiscal ticket_id=%s",
            ticket.get("id"),
        )
        raise RafaelFiscalError(f"No se pudo persistir documento fiscal RAFAEL: {exc}") from exc


def _log_sale_created(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: Optional[int],
    ticket_id: Optional[str],
    tpv_sale_id: int,
    payload: Dict[str, Any],
    rafael_result: Dict[str, Any],
) -> None:
    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name="RAFAEL",
            action_type="sale_created",
            action_description=f"Venta TPV registrada en RAFAEL: {ticket_id}",
            details={
                "ticket_id": ticket_id,
                "sale_id": tpv_sale_id,
                "company_id": company_id,
                "user_id": user_id,
                "payment_method": payload.get("payment_method"),
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
        logger.exception("Activity log sale_created failed ticket_id=%s", ticket_id)
