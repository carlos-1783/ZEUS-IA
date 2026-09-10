"""
⚖️ JUSTICIA Automation Handler
Ejecuta trabajo legal real (GDPR + documentos pendientes en BD) para las
actividades genéricas que el motor de workflows (teamflow_engine.py) dispara
para JUSTICIA: task_assigned / document_reviewed / compliance_check.

Historial: antes devolvía SIEMPRE el mismo texto fijo de política de
privacidad / términos de servicio, sin leer ni escribir nada en BD, con
"docs_generated": 3 hardcodeado -- el mismo patrón "toolkit legal = stub"
ya cerrado en POST /api/v1/justice/contracts/generate, pero seguía vivo en
esta ruta (la que ejecutan de verdad los pasos "legal_review" /
"gdpr_validation" / "legal_stamp" de teamflow_engine.py). Ver
AUDIT_JUSTICIA_ESTADO_FINAL.md para la evidencia completa.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.agent_activity import AgentActivity
from app.models.user import User

logger = logging.getLogger(__name__)


def _user_from_activity(session: Session, activity: AgentActivity) -> Optional[User]:
    details = activity.details if isinstance(activity.details, dict) else {}
    uid = details.get("user_id")
    if uid:
        user = session.query(User).filter(User.id == int(uid)).first()
        if user:
            return user
    email = (activity.user_email or "").strip()
    if email:
        return session.query(User).filter(User.email == email).first()
    return None


def _payload(activity: AgentActivity) -> Dict[str, Any]:
    details = activity.details if isinstance(activity.details, dict) else {}
    inner = details.get("payload")
    if isinstance(inner, dict):
        return {**details, **inner}
    return details


def handle_justicia_task(activity: AgentActivity) -> Dict[str, Any]:
    """Auditoría GDPR real + documentos pendientes reales, scopeados al usuario
    real de la actividad. Si el payload trae un `document_id`, intenta también
    aplicar firma real (mismo servicio que usa POST /api/v1/justice/sign)."""
    session = SessionLocal()
    try:
        user = _user_from_activity(session, activity)
        if not user:
            return {
                "status": "failed",
                "details_update": {
                    "real_execution": False,
                    "error": "Usuario no encontrado para tarea JUSTICIA",
                },
                "notes": (
                    "No se pudo resolver el usuario asociado a la actividad "
                    "(activity.user_email/user_id); no se ejecuta ninguna "
                    "acción legal simulada en su lugar."
                ),
            }

        from services.gdpr_engine import run_gdpr_check
        from services.justice_audit_service import list_documents, list_pending_documents_grouped

        gdpr = run_gdpr_check(session, user, systems=[])
        pending = list_pending_documents_grouped(session, user)
        recent_docs = list_documents(session, user, limit=10)

        signature_result: Optional[Dict[str, Any]] = None
        signature_error: Optional[str] = None
        payload = _payload(activity)
        document_id = payload.get("document_id")
        if document_id:
            try:
                from services.signature_service import apply_signature

                signature_result = apply_signature(
                    session,
                    user,
                    document_id=document_id,
                    document_name=payload.get("document_name") or "",
                    file_hash=payload.get("file_hash") or "",
                    signer_label=payload.get("signer") or "JUSTICIA",
                )
            except HTTPException as exc:
                signature_error = str(exc.detail)

        session.commit()

        issues = gdpr.get("issues") or []
        summary = (
            f"Revisión legal real: {len(issues)} hallazgo(s) GDPR, "
            f"{pending.get('total_pending', 0)} documento(s) pendiente(s) de aprobación."
        )
        if signature_result:
            summary += f" Documento {signature_result.get('document_id')} firmado."
        elif signature_error:
            summary += f" Firma solicitada no aplicada: {signature_error}."

        return {
            "status": "completed",
            "details_update": {
                "automation": {
                    "gdpr_issues": issues,
                    "pending_documents": pending,
                    "recent_legal_documents": recent_docs,
                    "signature": signature_result,
                    "signature_error": signature_error,
                    "summary": summary,
                },
                "real_execution": True,
                "data_origin": "database",
            },
            "metrics_update": {
                "gdpr_alerts_created": gdpr.get("alerts_created", 0),
                "pending_documents_total": pending.get("total_pending", 0),
                "documents_signed": 1 if signature_result else 0,
            },
            "notes": summary,
            "executed_handler": "gdpr_engine.run_gdpr_check+justice_audit_service.list_pending_documents_grouped",
        }
    except Exception as exc:  # pragma: no cover - defensive, error real reportado
        session.rollback()
        logger.exception("handle_justicia_task failed for activity_id=%s", getattr(activity, "id", None))
        return {
            "status": "failed",
            "details_update": {"real_execution": False, "error": str(exc)},
            "notes": f"Error ejecutando revisión legal real: {exc}",
        }
    finally:
        session.close()
