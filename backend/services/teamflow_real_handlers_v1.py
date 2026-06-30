"""Real TeamFlow / automation handlers — replace GENERIC_INTERNAL for critical actions."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.db.session import SessionLocal
from app.models.agent_activity import AgentActivity
from app.models.document_approval import DocumentApproval
from app.models.user import User

logger = logging.getLogger(__name__)

HANDLER_NAME = "TEAMFLOW_REAL_HANDLER"


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
    inner = details.get("payload")
    if isinstance(inner, dict):
        return {**details, **inner}
    return details


def _ok(result: Dict[str, Any], *, handler: str = HANDLER_NAME) -> Dict[str, Any]:
    return {
        "status": "completed",
        "details_update": {"real_handler": result, "real_execution": True},
        "metrics_update": result.get("metrics") or {},
        "notes": result.get("message") or "Acción real ejecutada.",
        "executed_handler": handler,
    }


def _fail(msg: str) -> Dict[str, Any]:
    return {
        "status": "failed",
        "details_update": {"real_execution": False, "error": msg},
        "notes": msg,
        "executed_handler": HANDLER_NAME,
    }


def handle_contract_creator_rrhh(activity: AgentActivity) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        user = _user_from_activity(session, activity)
        if not user:
            return _fail("Usuario no encontrado para contract_creator_rrhh")
        data = _payload(activity)
        from services.contract_generator import generate_contract

        parties = data.get("parties") or [
            data.get("employee_name") or "Empleado",
            data.get("company_name") or "Empresa",
        ]
        if isinstance(parties, str):
            parties = [p.strip() for p in parties.split(",") if p.strip()]
        result = generate_contract(
            session,
            user,
            parties=list(parties),
            scope=data.get("role") or data.get("scope") or "contrato laboral RRHH",
            media_buying=False,
        )
        session.commit()
        return _ok(
            {"message": "Contrato RRHH generado en legal_documents", **result},
            handler="rrhh_service.create_contract",
        )
    except Exception as exc:
        session.rollback()
        logger.exception("contract_creator_rrhh failed")
        return _fail(str(exc))
    finally:
        session.close()


def handle_invoice_sent(activity: AgentActivity) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        user = _user_from_activity(session, activity)
        if not user:
            return _fail("Usuario no encontrado para invoice_sent")
        data = _payload(activity)
        title = data.get("invoice_number") or f"INV-{activity.id}"
        doc = DocumentApproval(
            user_id=user.id,
            agent_name="RAFAEL",
            document_type="fiscal_document",
            title=str(title)[:255],
            content=json.dumps(
                {
                    "invoice_template": data,
                    "workflow_id": data.get("workflow_id"),
                    "execution_id": data.get("execution_id"),
                },
                ensure_ascii=False,
                default=str,
            ),
            status="pending_review",
            fiscal_document_type="factura",
        )
        session.add(doc)
        session.flush()
        session.commit()
        return _ok(
            {
                "message": f"Factura persistida (#{doc.id})",
                "document_approval_id": doc.id,
                "metrics": {"invoices_persisted": 1},
            },
            handler="rafael_service.send_invoice",
        )
    except Exception as exc:
        session.rollback()
        return _fail(str(exc))
    finally:
        session.close()


def handle_document_signed(activity: AgentActivity) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        user = _user_from_activity(session, activity)
        if not user:
            return _fail("Usuario no encontrado para document_signed")
        data = _payload(activity)
        from services.signature_service import apply_signature
        from services.zeus_event_bus_v1 import emit_event

        result = apply_signature(
            session,
            user,
            document_id=data.get("document_id"),
            document_name=data.get("document_name") or "documento.pdf",
            file_hash=data.get("file_hash") or "",
            signer_label=data.get("signer") or "JUSTICIA",
        )
        emit_event(
            session,
            user,
            event_name="document_signed",
            source_module="JUSTICIA",
            payload={**result, "owner_agent": "JUSTICIA"},
        )
        session.commit()
        return _ok(
            {**result, "message": "Documento firmado y evento propagado"},
            handler="justicia_service.sign_document",
        )
    except Exception as exc:
        session.rollback()
        return _fail(str(exc))
    finally:
        session.close()


def handle_contract_generator(activity: AgentActivity) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        user = _user_from_activity(session, activity)
        if not user:
            return _fail("Usuario no encontrado")
        data = _payload(activity)
        from services.contract_generator import generate_contract

        parties = data.get("parties") or ["Parte A", "Parte B"]
        if isinstance(parties, str):
            parties = [p.strip() for p in parties.split(",")]
        result = generate_contract(
            session,
            user,
            parties=parties,
            scope=data.get("scope") or "servicios",
            media_buying=bool(data.get("media_buying")),
        )
        session.commit()
        return _ok(result, handler="justicia_service.generate_contract")
    except Exception as exc:
        session.rollback()
        return _fail(str(exc))
    finally:
        session.close()


def handle_image_analyzer(activity: AgentActivity) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        data = _payload(activity)
        url = data.get("image_url") or data.get("url")
        if not url:
            return _fail("image_analyzer requiere image_url en payload")
        from services.perseo_ai_service_v2 import analyze_image_ai

        result = analyze_image_ai({"image_url": url, "goals": data.get("goals") or ["conversion"], "tags": []})
        return _ok(
            {"message": "Análisis de imagen completado", "analysis": result},
            handler="perseo_service.analyze_image",
        )
    except Exception as exc:
        return _fail(str(exc))
    finally:
        session.close()


def handle_ads_campaign_builder(activity: AgentActivity) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        user = _user_from_activity(session, activity)
        if not user:
            return _fail("Usuario no encontrado")
        data = _payload(activity)
        channels = data.get("channels")
        platform = data.get("platform") or (channels[0] if isinstance(channels, list) and channels else "meta")
        name = data.get("campaign_name") or data.get("name") or f"Campaign-{activity.id}"
        budget = float(data.get("budget") or 50)

        doc = DocumentApproval(
            user_id=user.id,
            agent_name="PERSEO",
            document_type="marketing_campaign",
            title=str(name)[:255],
            content=json.dumps(
                {"platform": platform, "budget": budget, "plan": data, "real_execution": True},
                ensure_ascii=False,
                default=str,
            ),
            status="draft",
        )
        session.add(doc)
        session.flush()

        ads_result: Dict[str, Any] = {"persisted_local": True, "document_approval_id": doc.id}
        try:
            from services.perseo_ads_engine_v2 import create_ad_campaign

            ads_result = create_ad_campaign(session, user, platform=str(platform), name=str(name), budget=budget)
        except Exception as api_exc:
            ads_result["external_api"] = {"skipped": True, "reason": str(api_exc)}

        session.commit()
        return _ok(
            {"message": "Campaña ads persistida", **ads_result},
            handler="perseo_service.create_campaign",
        )
    except Exception as exc:
        session.rollback()
        return _fail(str(exc))
    finally:
        session.close()


def handle_unmapped_no_fake(activity: AgentActivity) -> Dict[str, Any]:
    return _fail(f"Sin handler real para {activity.agent_name}/{activity.action_type}")


TEAMFLOW_REAL_ACTION_TYPES = frozenset(
    {
        "contract_creator_rrhh",
        "invoice_sent",
        "document_signed",
        "contract_generator",
        "image_analyzer",
        "ads_campaign_builder",
    }
)
