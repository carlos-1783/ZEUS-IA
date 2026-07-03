"""ZEUS event bus — per-module handlers (async-safe, best-effort)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.compliance_event import ComplianceEvent
from app.models.user import User

logger = logging.getLogger(__name__)


def handle_ops_employee_shadow(db: Session, user: Optional[User], payload: Dict[str, Any]) -> bool:
    """OPS shadow record when RRHH creates employee."""
    try:
        emp = payload.get("employee") or {}
        db.add(
            ComplianceEvent(
                event_type="ops_employee_shadow",
                severity="info",
                source="OPS",
                details_json=json.dumps(
                    {
                        "employee_id": emp.get("id"),
                        "employee_code": emp.get("employee_code"),
                        "full_name": emp.get("full_name"),
                        "shadow": True,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
        )
        db.flush()
        return True
    except Exception as exc:
        logger.warning("[EVENT_HANDLER] ops shadow failed: %s", exc)
        return False


def handle_workspace_create_task(
    db: Session,
    user: Optional[User],
    event_name: str,
    payload: Dict[str, Any],
) -> bool:
    if not user:
        return False
    try:
        from services.afrodita_workspace_db_service_v1 import persist_workspace_playbook, workspace_enabled

        if not workspace_enabled():
            return False
        persist_workspace_playbook(
            db,
            user,
            title=f"Task:{event_name}",
            content={"event": event_name, "task_type": "cross_module", **payload},
            agent_source=payload.get("owner_agent") or "ZEUS_CORE",
        )
        return True
    except Exception as exc:
        logger.warning("[EVENT_HANDLER] workspace task failed: %s", exc)
        return False


def handle_justicia_compliance(db: Session, event_name: str, payload: Dict[str, Any]) -> bool:
    try:
        db.add(
            ComplianceEvent(
                event_type=event_name,
                severity="low",
                source=payload.get("source_agent") or payload.get("owner_agent") or "JUSTICIA",
                details_json=json.dumps(payload, ensure_ascii=False, default=str),
            )
        )
        db.flush()
        return True
    except Exception as exc:
        logger.warning("[EVENT_HANDLER] justicia compliance failed: %s", exc)
        return False


def handle_perseo_notification(db: Session, event_name: str, payload: Dict[str, Any]) -> bool:
    try:
        db.add(
            ComplianceEvent(
                event_type=f"perseo_notify_{event_name}",
                severity="info",
                source="PERSEO",
                details_json=json.dumps(payload, ensure_ascii=False, default=str),
            )
        )
        db.flush()
        return True
    except Exception as exc:
        logger.warning("[EVENT_HANDLER] perseo notification failed: %s", exc)
        return False


def handle_workspace_financial_task(db: Session, user: Optional[User], payload: Dict[str, Any]) -> bool:
    return handle_workspace_create_task(db, user, "invoice_generated", {**payload, "task_type": "financial"})


def handle_workspace_mark_complete(db: Session, user: Optional[User], payload: Dict[str, Any]) -> bool:
    return handle_workspace_create_task(
        db,
        user,
        "contract_signed",
        {**payload, "task_type": "complete", "status": "completed"},
    )


def handle_payment_risk_agents(
    db: Session,
    user: Optional[User],
    payload: Dict[str, Any],
) -> bool:
    """RAFAEL notify + JUSTICIA contract review + THALOS monitor (TeamFlow)."""
    if not user:
        return False
    try:
        from services.teamflow_persistence_v1 import create_item

        base = {
            "customer_id": payload.get("customer_id"),
            "name": payload.get("name"),
            "email": payload.get("email"),
            "next_payment_date": payload.get("next_payment_date"),
            "risk_level": payload.get("risk_level"),
        }
        create_item(
            db,
            user,
            owner_agent="RAFAEL",
            source_agent="CRM",
            target_agent="RAFAEL",
            title=f"Aviso cobro — {payload.get('name') or 'cliente'}",
            item_type="payment_reminder",
            status="pending",
            content={**base, "action": "notify_client"},
        )
        create_item(
            db,
            user,
            owner_agent="JUSTICIA",
            source_agent="CRM",
            target_agent="JUSTICIA",
            title=f"Revisión contrato/cliente — {payload.get('name') or 'cliente'}",
            item_type="client_legal_review",
            status="pending",
            content={**base, "action": "review_contract"},
        )
        create_item(
            db,
            user,
            owner_agent="THALOS",
            source_agent="CRM",
            target_agent="THALOS",
            title=f"Riesgo pago — {payload.get('name') or 'cliente'}",
            item_type="payment_risk",
            status="pending",
            content=base,
        )
        db.add(
            ComplianceEvent(
                event_type="payment_risk",
                severity="high" if payload.get("risk_level") == "high" else "medium",
                source="THALOS",
                details_json=json.dumps(payload, ensure_ascii=False, default=str),
            )
        )
        try:
            from services.zeus_analytics_real_v1 import record_zeus_alert, record_zeus_event

            record_zeus_alert(
                db,
                level=payload.get("risk_level") or "medium",
                message=f"Riesgo pago — {payload.get('name') or 'cliente'}",
                user_id=user.id,
            )
            record_zeus_event(
                db,
                event_type="alert_triggered",
                agent="THALOS",
                status="success",
                user_id=user.id,
            )
        except Exception:
            pass
        db.flush()
        return True
    except Exception as exc:
        logger.warning("[EVENT_HANDLER] payment_risk agents failed: %s", exc)
        return False


def handle_perseo_client_created(db: Session, user: Optional[User], payload: Dict[str, Any]) -> bool:
    return handle_perseo_notification(db, "client_created", payload)


def dispatch_event_handlers(
    db: Session,
    user: Optional[User],
    event_name: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Run registered handlers for an event. Returns handlers run + optional pipeline result."""
    done: List[str] = []
    pipeline: Optional[Dict[str, Any]] = None
    normalized = "document_signed" if event_name == "contract_signed" else event_name

    if normalized == "employee_created":
        if handle_ops_employee_shadow(db, user, payload):
            done.append("ops.create_employee_shadow")
        if handle_workspace_create_task(db, user, normalized, payload):
            done.append("workspace.create_task")
        if handle_justicia_compliance(db, "employee_created", payload):
            done.append("justicia.generate_contract")

    elif normalized in ("contract_rrhh_created", "document_signed", "contract_signed"):
        if handle_workspace_mark_complete(db, user, payload) or handle_workspace_create_task(
            db, user, normalized, payload
        ):
            done.append("workspace.mark_complete" if normalized != "contract_rrhh_created" else "workspace.create_task")
        if handle_justicia_compliance(db, normalized, payload):
            done.append("justicia.compliance_record")
        if normalized in ("document_signed", "contract_signed"):
            if handle_perseo_notification(db, normalized, payload):
                done.append("perseo.send_notification")
        if normalized == "contract_rrhh_created":
            try:
                from services.zeus_document_pipeline_v1 import run_document_pipeline

                pipeline = run_document_pipeline(db, user, event_type=normalized, payload=payload)
                done.append("pipeline.perseo_rafael_thalos")
            except Exception as exc:
                logger.warning("[EVENT_HANDLER] document pipeline failed: %s", exc)

    elif normalized == "invoice_generated":
        if handle_workspace_financial_task(db, user, payload):
            done.append("workspace.create_financial_task")

    elif normalized == "policy_expiring":
        if handle_workspace_create_task(db, user, normalized, payload):
            done.append("workspace.create_task")
        if handle_perseo_notification(db, normalized, payload):
            done.append("perseo.send_reminder")

    elif normalized == "ops_route_created":
        if handle_workspace_create_task(db, user, normalized, payload):
            done.append("workspace.create_task")

    elif normalized == "client_created":
        if handle_workspace_create_task(db, user, normalized, payload):
            done.append("workspace.create_task")
        if handle_perseo_client_created(db, user, payload):
            done.append("perseo.client_onboarding")

    elif normalized == "client_updated":
        if handle_workspace_create_task(db, user, normalized, payload):
            done.append("workspace.create_task")

    elif normalized == "payment_risk":
        if handle_payment_risk_agents(db, user, payload):
            done.append("rafael.notify_client")
            done.append("justicia.review_contract")
            done.append("thalos.monitor")

    return {"handlers": done, "pipeline": pipeline}
