"""Real production handlers for TeamFlow critical action_types (phase 2)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.db.session import SessionLocal
from app.models.agent_activity import AgentActivity
from app.models.legal_document import LegalDocument
from app.models.user import User

from .generic_internal import GENERIC_INTERNAL_HANDLER_NAME, handle_generic_internal

logger = logging.getLogger(__name__)

HANDLER_NAME = "PRODUCTION_REAL_V1"


def _user_from_activity(session, activity: AgentActivity) -> Optional[User]:
    details = activity.details if isinstance(activity.details, dict) else {}
    uid = details.get("user_id")
    if uid:
        user = session.query(User).filter(User.id == int(uid)).first()
        if user:
            return user
    email = (activity.user_email or "").strip()
    if email:
        return session.query(User).filter(User.email == email).first()
    return session.query(User).filter(User.is_superuser.is_(True)).first()


def _payload(activity: AgentActivity) -> Dict[str, Any]:
    details = activity.details if isinstance(activity.details, dict) else {}
    inner = details.get("payload") if isinstance(details.get("payload"), dict) else {}
    return {**details, **inner}


def _fallback(activity: AgentActivity, exc: Exception) -> Dict[str, Any]:
    logger.warning(
        "[PRODUCTION_REAL] fallback generic for %s/%s: %s",
        activity.agent_name,
        activity.action_type,
        exc,
    )
    out = handle_generic_internal(activity)
    out["notes"] = f"Real handler failed ({exc}); {out.get('notes', '')}"
    out["executed_handler"] = f"{HANDLER_NAME}_FALLBACK_{GENERIC_INTERNAL_HANDLER_NAME}"
    return out


def handle_contract_creator_rrhh(activity: AgentActivity) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        user = _user_from_activity(db, activity)
        if not user:
            raise ValueError("user not found")
        p = _payload(activity)
        from services.workspaces.afrodita_tools import create_rrhh_contract

        contract = create_rrhh_contract(
            {
                "employee_name": p.get("employee_name") or p.get("full_name") or "Empleado",
                "role": p.get("role") or p.get("role_title") or "Puesto",
                "salary": float(p.get("salary") or 0),
                "contract_type": p.get("contract_type") or "indefinido",
            }
        )
        from services.contract_generator import generate_contract

        legal = generate_contract(
            db,
            user,
            parties=[str(contract["clauses"][0]), str(contract["clauses"][1])],
            scope=f"Contrato laboral {p.get('contract_type', 'indefinido')}",
        )
        from services.zeus_cross_module_events_v1 import emit_cross_module_event

        emit_cross_module_event(
            db,
            user,
            "contract_rrhh_created",
            {"source": "contract_creator_rrhh", "contract": contract, "legal": legal},
        )
        db.commit()
        return {
            "status": "completed",
            "executed_handler": HANDLER_NAME,
            "details_update": {"contract": contract, "legal_document": legal, "real_execution": True},
            "metrics_update": {"contracts_created": 1},
            "notes": "Contrato RRHH persistido en legal_documents",
        }
    except Exception as exc:
        db.rollback()
        return _fallback(activity, exc)
    finally:
        db.close()


def handle_invoice_sent(activity: AgentActivity) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        user = _user_from_activity(db, activity)
        if not user:
            raise ValueError("user not found")
        p = _payload(activity)
        invoice_number = p.get("invoice_number") or f"INV-{datetime.now(timezone.utc):%Y%m%d}-001"
        content = json.dumps(
            {
                "invoice_number": invoice_number,
                "customer": p.get("customer") or p.get("client_name") or "Cliente",
                "currency": p.get("currency") or "EUR",
                "tax_rate": p.get("tax_rate") or 21,
                "status": "sent",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        )
        row = LegalDocument(
            user_id=user.id,
            doc_type="fiscal_invoice",
            content=content,
            status="approved",
            owner_agent="RAFAEL",
        )
        db.add(row)
        db.flush()
        from services.workspace_playbook_writer_v1 import write_ops_playbook

        write_ops_playbook(
            db,
            user,
            action="invoice_sent",
            title=f"Factura {invoice_number}",
            payload={"document_id": row.public_id, "invoice_number": invoice_number},
        )
        db.commit()
        return {
            "status": "completed",
            "executed_handler": HANDLER_NAME,
            "details_update": {
                "document_id": row.public_id,
                "invoice_number": invoice_number,
                "real_execution": True,
                "stored_in_db": True,
            },
            "metrics_update": {"invoices_sent": 1},
            "notes": f"Factura {invoice_number} persistida",
        }
    except Exception as exc:
        db.rollback()
        return _fallback(activity, exc)
    finally:
        db.close()


def handle_document_signed(activity: AgentActivity) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        user = _user_from_activity(db, activity)
        if not user:
            raise ValueError("user not found")
        p = _payload(activity)
        from services.signature_service import apply_signature

        signed = apply_signature(
            db,
            user,
            document_id=p.get("document_id"),
            document_name=str(p.get("document_name") or "documento.pdf"),
            file_hash=str(p.get("file_hash") or ""),
            signer_label=str(p.get("signer") or "JUSTICIA"),
        )
        db.commit()
        return {
            "status": "completed",
            "executed_handler": HANDLER_NAME,
            "details_update": signed,
            "metrics_update": {"documents_signed": 1},
            "notes": "Documento firmado y propagado",
        }
    except Exception as exc:
        db.rollback()
        return _fallback(activity, exc)
    finally:
        db.close()


def handle_ads_campaign_builder(activity: AgentActivity) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        user = _user_from_activity(db, activity)
        if not user:
            raise ValueError("user not found")
        p = _payload(activity)
        from services.perseo_ai_service_v2 import generate_ads_ai

        ads = generate_ads_ai(
            {
                "brand": p.get("brand") or "ZEUS IA",
                "channels": p.get("channels") or ["Meta", "Google"],
                "budget": p.get("budget") or p.get("budget_mode") or "sandbox",
                "objective": p.get("objective") or "conversion",
            }
        )
        from services.workspace_playbook_service_v1 import persist_execution_playbook

        row = persist_execution_playbook(
            db,
            user,
            agent_source="automation",
            action="ads_campaign_builder",
            title=f"Campaña {p.get('brand', 'ZEUS')}",
            payload=ads,
        )
        db.commit()
        return {
            "status": "completed",
            "executed_handler": HANDLER_NAME,
            "details_update": {"ads": ads, "playbook_id": row.id if row else None, "real_execution": True},
            "metrics_update": {"campaigns_built": 1},
            "notes": "Blueprint de campaña persistido",
        }
    except Exception as exc:
        db.rollback()
        return _fallback(activity, exc)
    finally:
        db.close()
