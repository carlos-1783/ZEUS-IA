"""
Bus de eventos ligero: registro + actividades para trazabilidad (RAFAEL/JUSTICIA en venta, PERSEO en registro).
No bloquea el flujo principal si falla el log.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def emit_payment_created(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: Optional[int],
    customer_id: Optional[int],
    ticket_id: Optional[str],
    tpv_sale_id: Optional[int],
    payment_method: Optional[str],
    amount: Optional[float] = None,
    service_name: Optional[str] = None,
    db: Optional[Session] = None,
) -> None:
    """Evento de cobro CMR oficina → analytics y trazabilidad global."""
    _ = db
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "company_id": company_id,
        "customer_id": customer_id,
        "ticket_id": ticket_id,
        "tpv_sale_id": tpv_sale_id,
        "payment_method": payment_method,
        "amount": amount,
        "service_name": service_name,
        "source": "CMR",
    }
    logger.info("event payment_created %s", payload)
    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name="RAFAEL",
            action_type="event_payment_created",
            action_description="Evento: cobro CMR registrado en motor fiscal",
            details=payload,
            metrics={"amount": amount} if amount is not None else None,
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
        ActivityLogger.log_activity(
            agent_name="ZEUS CORE",
            action_type="event_payment_created",
            action_description="Cobro oficina integrado en métricas globales",
            details=payload,
            metrics={"amount": amount} if amount is not None else None,
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
    except Exception as e:
        logger.warning("event_payment_created activity log failed: %s", e)


def emit_payment_registered(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: Optional[int],
    customer_id: Optional[int],
    ticket_id: Optional[str],
    tpv_sale_id: Optional[int],
    payment_method: Optional[str],
    amount: Optional[float] = None,
    service_name: Optional[str] = None,
    source: str = "UNKNOWN",
    db: Optional[Session] = None,
) -> None:
    """
    Evento canónico de pago registrado.
    Mantiene compatibilidad con emit_payment_created y añade trazabilidad común multi-módulo.
    """
    from services.zeus_core_guard_v1 import guard_enforce, validate_event_emit

    ev = validate_event_emit(
        "payment_registered",
        company_id=company_id,
        user_id=user_id,
        user_email=user_email,
        db=db,
        payload={"amount": amount, "source": source},
    )
    if not ev.allowed and guard_enforce():
        logger.warning("emit_payment_registered blocked: %s", ev.human_message)
        return

    _ = db
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "company_id": company_id,
        "customer_id": customer_id,
        "ticket_id": ticket_id,
        "tpv_sale_id": tpv_sale_id,
        "payment_method": payment_method,
        "amount": amount,
        "service_name": service_name,
        "source": source,
    }
    logger.info("event payment_registered %s", payload)
    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name="RAFAEL",
            action_type="event_payment_registered",
            action_description=f"Evento canónico: pago registrado ({source})",
            details=payload,
            metrics={"amount": amount} if amount is not None else None,
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
        ActivityLogger.log_activity(
            agent_name="ZEUS CORE",
            action_type="event_payment_registered",
            action_description="Sincronización de pago para CRM/analytics",
            details=payload,
            metrics={"amount": amount} if amount is not None else None,
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
    except Exception as e:
        logger.warning("event_payment_registered activity log failed: %s", e)


def emit_client_created(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: int,
    customer_id: int,
    customer_name: Optional[str] = None,
    customer_email: Optional[str] = None,
    db: Optional[Session] = None,
) -> None:
    """Evento canónico: cliente CRM creado."""
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "company_id": company_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
    }
    logger.info("event client_created %s", payload)
    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name="ZEUS CORE",
            action_type="client_created",
            action_description=f"Cliente creado: {customer_name or customer_id}",
            details=payload,
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
    except Exception as e:
        logger.warning("event client_created activity log failed: %s", e)
    _ = db


def emit_invoice_generated(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: Optional[int],
    invoice_id: int,
    file_path: str,
    file_size: int,
    db: Optional[Session] = None,
) -> None:
    _ = db
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "company_id": company_id,
        "invoice_id": invoice_id,
        "file_path": file_path,
        "file_size": file_size,
    }
    logger.info("event invoice_generated %s", payload)
    try:
        from services.activity_logger import ActivityLogger
        from services.zeus_office_mode import translate_activity

        ActivityLogger.log_activity(
            agent_name="RAFAEL",
            action_type="invoice_generated",
            action_description=translate_activity("invoice_generated"),
            details=payload,
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
    except Exception as e:
        logger.warning("emit_invoice_generated failed: %s", e)


def emit_model_303_generated(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: Optional[int],
    period: str,
    file_path: str,
    file_size: int,
    resultado: float,
    db: Optional[Session] = None,
) -> None:
    _ = db
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "company_id": company_id,
        "period": period,
        "file_path": file_path,
        "file_size": file_size,
        "resultado": resultado,
    }
    logger.info("event model_303_generated %s", payload)
    try:
        from services.activity_logger import ActivityLogger
        from services.zeus_office_mode import translate_activity

        ActivityLogger.log_activity(
            agent_name="RAFAEL",
            action_type="tax_model_303_generated",
            action_description=translate_activity("tax_model_303_generated"),
            details=payload,
            metrics={"resultado": resultado},
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
    except Exception as e:
        logger.warning("emit_model_303_generated failed: %s", e)


def emit_cashflow_updated(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: Optional[int],
    amount: float,
    direction: str = "in",
    source: str = "OFFICE",
    customer_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
    tpv_sale_id: Optional[int] = None,
    ticket_id: Optional[str] = None,
    payment_method: Optional[str] = None,
    db: Optional[Session] = None,
) -> None:
    """Persiste movimiento en cashflow_ledger y registra actividad."""
    from services.zeus_core_guard_v1 import guard_enforce, validate_event_emit

    ev = validate_event_emit(
        "cashflow_updated",
        company_id=company_id,
        user_id=user_id,
        user_email=user_email,
        db=db,
        payload={"amount": amount, "direction": direction, "source": source},
    )
    if not ev.allowed and guard_enforce():
        logger.warning("emit_cashflow_updated blocked: %s", ev.human_message)
        return

    payload: Dict[str, Any] = {
        "user_id": user_id,
        "company_id": company_id,
        "customer_id": customer_id,
        "invoice_id": invoice_id,
        "tpv_sale_id": tpv_sale_id,
        "ticket_id": ticket_id,
        "amount": amount,
        "direction": direction,
        "source": source,
        "payment_method": payment_method,
    }
    logger.info("event cashflow_updated %s", payload)

    ledger_id = None
    if db is not None and company_id is not None and float(amount or 0) > 0:
        try:
            from services.cashflow_ledger_service import record_movement

            entry = record_movement(
                db,
                company_id=int(company_id),
                amount=float(amount),
                direction=direction,
                source=source,
                user_id=user_id,
                customer_id=customer_id,
                invoice_id=invoice_id,
                tpv_sale_id=tpv_sale_id,
                ticket_id=ticket_id,
                payment_method=payment_method,
                auto_commit=True,
            )
            ledger_id = entry.id
            payload["ledger_entry_id"] = ledger_id
        except Exception as e:
            logger.warning("cashflow_ledger persist failed: %s", e)

    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name="RAFAEL",
            action_type="cashflow_updated",
            action_description=f"Cashflow actualizado ({direction}): {amount:.2f} €",
            details=payload,
            metrics={"amount": amount, "ledger_entry_id": ledger_id},
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
    except Exception as e:
        logger.warning("emit_cashflow_updated failed: %s", e)


def emit_sale_created(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: Optional[int],
    ticket_id: Optional[str],
    tpv_sale_id: Optional[int],
    payment_method: Optional[str],
    db: Optional[Session] = None,
) -> None:
    _ = db  # reservado si en el futuro se reutiliza la sesión del request
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "company_id": company_id,
        "ticket_id": ticket_id,
        "tpv_sale_id": tpv_sale_id,
        "payment_method": payment_method,
    }
    logger.info("event sale_created %s", payload)
    try:
        from services.activity_logger import ActivityLogger

        for agent in ("RAFAEL", "JUSTICIA"):
            ActivityLogger.log_activity(
                agent_name=agent,
                action_type="event_sale_created",
                action_description="Evento: venta TPV registrada (snapshot fiscal)",
                details=payload,
                user_email=user_email,
                status="completed",
                priority="normal",
                visible_to_client=True,
            )
    except Exception as e:
        logger.warning("event_sale_created activity log failed: %s", e)


def emit_user_registered(
    *,
    user_id: int,
    user_email: Optional[str],
    company_name: Optional[str],
    db: Optional[Session] = None,
) -> None:
    _ = db
    payload = {"user_id": user_id, "company_name": company_name}
    logger.info("event user_registered %s", payload)
    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name="PERSEO",
            action_type="event_user_registered",
            action_description="Evento: nuevo usuario registrado (activación marketing/onboarding)",
            details=payload,
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
    except Exception as e:
        logger.warning("event_user_registered activity log failed: %s", e)


def emit_time_control_event(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: Optional[int],
    employee_id: str,
    event_type: str,
    record_id: Optional[int],
    details: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> None:
    """Trazabilidad Afrodita / RR.HH. a través del feed de actividades (no bloquea fichaje)."""
    _ = db
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "company_id": company_id,
        "employee_id": employee_id,
        "event_type": event_type,
        "record_id": record_id,
    }
    if details:
        payload["details"] = details
    logger.info("event time_control %s", payload)
    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name="AFRODITA",
            action_type="event_time_control",
            action_description=f"Control horario: {event_type} ({employee_id})",
            details=payload,
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
    except Exception as e:
        logger.warning("event_time_control activity log failed: %s", e)


def _log_time_cost_activity(
    *,
    action_type: str,
    description: str,
    user_email: Optional[str],
    payload: Dict[str, Any],
) -> None:
    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name="AFRODITA",
            action_type=action_type,
            action_description=description,
            details=payload,
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
    except Exception as e:
        logger.warning("%s activity log failed: %s", action_type, e)


def emit_employee_checked_in(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: int,
    employee_id: str,
    checkin_id: int,
    db: Optional[Session] = None,
) -> None:
    _ = db
    payload = {
        "user_id": user_id,
        "company_id": company_id,
        "employee_id": employee_id,
        "checkin_id": checkin_id,
    }
    logger.info("event employee_checked_in %s", payload)
    _log_time_cost_activity(
        action_type="checkin_registered",
        description=f"Fichaje registrado ({employee_id})",
        user_email=user_email,
        payload=payload,
    )


def emit_session_started(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: int,
    employee_id: str,
    session_id: int,
    db: Optional[Session] = None,
) -> None:
    _ = db
    payload = {
        "user_id": user_id,
        "company_id": company_id,
        "employee_id": employee_id,
        "session_id": session_id,
    }
    logger.info("event session_started %s", payload)
    _log_time_cost_activity(
        action_type="session_created",
        description=f"Sesión laboral iniciada ({employee_id})",
        user_email=user_email,
        payload=payload,
    )


def emit_session_closed(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: int,
    employee_id: str,
    session_id: int,
    total_hours: Optional[float],
    total_cost: Optional[float],
    db: Optional[Session] = None,
) -> None:
    _ = db
    payload = {
        "user_id": user_id,
        "company_id": company_id,
        "employee_id": employee_id,
        "session_id": session_id,
        "total_hours": total_hours,
        "total_cost": total_cost,
    }
    logger.info("event session_closed %s", payload)
    _log_time_cost_activity(
        action_type="session_closed",
        description=f"Sesión laboral cerrada ({employee_id})",
        user_email=user_email,
        payload=payload,
    )


def emit_cost_updated(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: int,
    employee_id: str,
    cost: float,
    hours: Optional[float],
    db: Optional[Session] = None,
) -> None:
    _ = db
    payload = {
        "user_id": user_id,
        "company_id": company_id,
        "employee_id": employee_id,
        "cost_eur": cost,
        "hours": hours,
    }
    logger.info("event cost_updated %s", payload)
    _log_time_cost_activity(
        action_type="cost_calculated",
        description=f"Coste laboral actualizado ({employee_id})",
        user_email=user_email,
        payload=payload,
    )


def emit_alert_triggered(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: int,
    employee_id: str,
    alert_type: str,
    detail: str,
    db: Optional[Session] = None,
) -> None:
    _ = db
    payload = {
        "user_id": user_id,
        "company_id": company_id,
        "employee_id": employee_id,
        "alert_type": alert_type,
        "detail": detail,
    }
    logger.info("event alert_triggered %s", payload)
    _log_time_cost_activity(
        action_type="alert_triggered",
        description=f"Alerta control horario: {alert_type}",
        user_email=user_email,
        payload=payload,
    )


def emit_scan_detected(
    *,
    user_id: int,
    user_email: Optional[str],
    company_id: int,
    scan_type: str,
    agent_name: str,
    trigger: str,
    details: Dict[str, Any],
    db: Optional[Session] = None,
) -> None:
    """Evento canónico: escaneo físico detectado (QR/NFC/DNI)."""
    _ = db
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "company_id": company_id,
        "scan_type": scan_type,
        "agent_name": agent_name,
        "trigger": trigger,
        **details,
    }
    logger.info("event scan_detected %s", payload)
    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name=agent_name,
            action_type=f"event_{trigger}",
            action_description=f"Escaneo {scan_type}: {trigger}",
            details=payload,
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
        ActivityLogger.log_activity(
            agent_name="ZEUS CORE",
            action_type=f"event_{trigger}",
            action_description=f"Pipeline scan → {agent_name}",
            details=payload,
            user_email=user_email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )
    except Exception as e:
        logger.warning("emit_scan_detected activity log failed: %s", e)
