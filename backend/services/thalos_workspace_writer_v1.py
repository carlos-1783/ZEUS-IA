"""Persiste resultados THALOS en workspace + thalos_workspace_items (thalos_workspace_connection_v1)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.thalos_workspace_item import ThalosWorkspaceItem
from services.workspace_deliverables import persist_workspace_deliverable, primary_company_id_for_user

logger = logging.getLogger(__name__)

ACTION_TO_TYPE = {
    "detect_suspicious_activity": "audit",
    "scan_security_logs": "audit",
    "security_scan": "audit",
    "security_monitor": "audit",
    "alert_admin": "alert",
    "task_assigned": "alert",
    "audit_cashflow_anomaly": "alert",
    "trigger_backup": "backup",
    "backup_created": "backup",
}


def workspace_write_enabled() -> bool:
    return bool(getattr(settings, "THALOS_WORKSPACE_WRITE_ENABLED", True))


def _payload_size_kb(payload: Dict[str, Any]) -> int:
    raw = json.dumps(payload, ensure_ascii=False)
    return max(1, len(raw.encode("utf-8")) // 1024)


def _status_from_payload(item_type: str, payload: Dict[str, Any]) -> str:
    if item_type == "backup":
        return "completed" if payload.get("backup_created") else "warning"
    if item_type == "alert":
        risk = str(payload.get("risk_level") or payload.get("severity") or "").lower()
        if risk in ("critical", "high"):
            return "critical"
        return "warning" if risk else "completed"
    risk = str(payload.get("risk_level") or "").lower()
    if risk == "critical":
        return "critical"
    if risk == "high":
        return "warning"
    alerts = payload.get("pattern_alerts") or payload.get("alerts") or []
    return "warning" if alerts else "completed"


def _normalize_content(item_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Estructura compatible con ThalosWorkspace.vue."""
    base: Dict[str, Any] = {
        "thalos_type": item_type,
        "executed_at": payload.get("executed_at") or datetime.now(timezone.utc).isoformat(),
        "file_size": _payload_size_kb(payload) * 1024,
        "result": payload.get("result") or payload.get("notes") or payload.get("message"),
    }
    if item_type == "audit":
        scan = payload.get("result") if isinstance(payload.get("result"), dict) else payload
        base.update(
            {
                "checks": payload.get("checks") or scan.get("checks"),
                "missing": payload.get("missing") or scan.get("missing"),
                "recommendations": payload.get("recommendations") or scan.get("recommendation"),
                "pattern_alerts": scan.get("pattern_alerts"),
                "failed_login_candidates": scan.get("failed_login_candidates"),
                "risk_level": scan.get("risk_level"),
            }
        )
    elif item_type == "alert":
        base.update(
            {
                "configuration": payload.get("configuration"),
                "actions_performed": payload.get("actions_performed"),
                "risk_score": payload.get("risk_score"),
                "events": payload.get("events"),
                "message": payload.get("message"),
                "severity": payload.get("severity"),
            }
        )
    elif item_type == "backup":
        bk = payload.get("result") if isinstance(payload.get("result"), dict) else payload
        base.update(
            {
                "backup_created": bk.get("backup_created", payload.get("backup_created")),
                "backup_path": bk.get("backup_path", payload.get("backup_path")),
                "source_exists": bk.get("source_exists", payload.get("source_exists")),
                "notes": bk.get("notes", payload.get("notes")),
            }
        )
    base["raw"] = payload
    return base


def write_workspace_item(
    db: Session,
    *,
    user_id: int,
    company_id: Optional[int],
    item_type: str,
    payload: Dict[str, Any],
    title: Optional[str] = None,
    source: str = "thalos_v1",
    action: Optional[str] = None,
    persist_document: bool = True,
) -> Optional[ThalosWorkspaceItem]:
    if not workspace_write_enabled():
        return None

    itype = (item_type or ACTION_TO_TYPE.get(action or "", "audit")).strip().lower()
    if itype not in ("audit", "alert", "backup"):
        itype = "audit"

    status = _status_from_payload(itype, payload)
    content = _normalize_content(itype, payload)
    size_kb = _payload_size_kb(payload)

    titles = {
        "audit": "Auditoría de seguridad THALOS",
        "alert": "Alerta de seguridad THALOS",
        "backup": "Backup del sistema THALOS",
    }
    doc_title = title or titles.get(itype, "Reporte THALOS")

    doc_id = None
    if persist_document and company_id:
        try:
            doc = persist_workspace_deliverable(
                db,
                user_id=user_id,
                company_id=company_id,
                agent_name="THALOS",
                workspace_category="legal_document",
                title=doc_title,
                content_type="legal_document",
                content={
                    **content,
                    "copy": content.get("result") or doc_title,
                    "format": "thalos_workspace_v1",
                    "file_size": size_kb * 1024,
                },
                status="draft",
                visible_in_workspace=True,
            )
            doc_id = doc.id
        except Exception:
            logger.exception("thalos workspace document persist failed")

    row = ThalosWorkspaceItem(
        item_type=itype,
        workspace_document_id=doc_id,
        company_id=company_id,
        user_id=user_id,
        status=status,
        data_size_kb=size_kb,
        title=doc_title,
        source=source,
        payload_json=json.dumps(payload, ensure_ascii=False),
    )
    db.add(row)
    db.flush()
    logger.info(
        "thalos workspace item id=%s type=%s status=%s size_kb=%s",
        row.id,
        itype,
        status,
        size_kb,
    )
    return row


def write_from_action_result(
    db: Session,
    *,
    user_id: int,
    company_id: Optional[int],
    action: str,
    result: Dict[str, Any],
    source: str = "thalos_executor",
) -> Optional[ThalosWorkspaceItem]:
    item_type = ACTION_TO_TYPE.get(action, "audit")
    payload = {**result, "action": action}
    if "result" in result and isinstance(result["result"], dict):
        payload = {**result["result"], "action": action, "executed": result.get("executed")}
    return write_workspace_item(
        db,
        user_id=user_id,
        company_id=company_id,
        item_type=item_type,
        payload=payload,
        source=source,
        action=action,
    )


def write_for_activity(
    db: Session,
    activity,
    *,
    action: str,
    result: Dict[str, Any],
    source: str = "automation",
) -> Optional[ThalosWorkspaceItem]:
    from app.models.user import User

    user = None
    if getattr(activity, "user_email", None):
        user = db.query(User).filter(User.email == activity.user_email).first()
    if not user:
        return None
    details = getattr(activity, "details", None) or {}
    cid = details.get("company_id") if isinstance(details, dict) else None
    return write_for_user(db, user, action=action, result=result, company_id=cid, source=source)


def write_for_user(
    db: Session,
    user,
    *,
    action: str,
    result: Dict[str, Any],
    company_id: Optional[int] = None,
    source: str = "thalos_v1",
) -> Optional[ThalosWorkspaceItem]:
    cid = company_id or primary_company_id_for_user(db, user)
    return write_from_action_result(
        db,
        user_id=user.id,
        company_id=cid,
        action=action,
        result=result,
        source=source,
    )
