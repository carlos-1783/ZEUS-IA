"""ZEUS document pipeline — PERSEO + RAFAEL + THALOS on real document events."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.compliance_event import ComplianceEvent
from app.models.user import User

logger = logging.getLogger(__name__)

HIGH_RISK_THRESHOLD = 0.7


def _document_content(doc: Dict[str, Any]) -> str:
    legal = doc.get("legal_document") if isinstance(doc.get("legal_document"), dict) else {}
    preview = legal.get("content_preview") or legal.get("content") or ""
    if isinstance(preview, str):
        return preview
    return json.dumps(preview, ensure_ascii=False, default=str)


def analyze_document_perseo(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Compliance heuristics on contract/legal text — real rules, no random stubs."""
    content = _document_content(doc).lower()
    recommendations: List[str] = []
    risk = 0.15

    if not content.strip():
        risk = 0.85
        recommendations.append("Documento sin contenido legible")
    else:
        if "rgpd" not in content and "2016/679" not in content:
            risk += 0.25
            recommendations.append("Añadir referencia explícita a RGPD")
        if "partes" not in content and "·" not in content:
            risk += 0.2
            recommendations.append("Verificar identificación de partes")
        if len(content) < 200:
            risk += 0.15
            recommendations.append("Contrato muy breve — revisar cláusulas")

    risk_score = min(round(risk, 2), 1.0)
    return {
        "agent_source": "PERSEO",
        "risk_score": risk_score,
        "compliance": risk_score < HIGH_RISK_THRESHOLD,
        "recommendations": recommendations,
        "real_execution": True,
    }


def process_financials_rafael(doc: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Map contract RRHH to fiscal follow-up (invoice / payroll cost estimate)."""
    data = payload if isinstance(payload, dict) else {}
    salary = float(data.get("salary") or 0)
    doc_type = str(data.get("contract_type") or doc.get("type") or "contract")
    is_contract = doc_type in ("contract", "contract_rrhh", "indefinido", "temporal") or bool(
        data.get("legal_document")
    )
    estimated = salary if salary > 0 else 0.0
    return {
        "agent_source": "RAFAEL",
        "invoice_required": bool(is_contract and estimated > 0),
        "estimated_value": estimated,
        "currency": "EUR",
        "real_execution": True,
    }


def monitor_event_thalos(
    db: Session,
    user: Optional[User],
    event_type: str,
    pipeline_slice: Dict[str, Any],
) -> Dict[str, Any]:
    """THALOS audit trail — persists compliance_event for monitoring."""
    analysis = pipeline_slice.get("analysis") or {}
    risk = float(analysis.get("risk_score") or 0)
    severity = "high" if risk >= HIGH_RISK_THRESHOLD else "info"
    try:
        db.add(
            ComplianceEvent(
                event_type=f"thalos_monitor_{event_type}",
                severity=severity,
                source="THALOS",
                details_json=json.dumps(
                    {
                        "event_type": event_type,
                        "risk_score": risk,
                        "pipeline": pipeline_slice,
                        "monitored": True,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
        )
        db.flush()
        return {"agent_source": "THALOS", "monitored": True, "severity": severity, "real_execution": True}
    except Exception as exc:
        logger.warning("[PIPELINE] thalos monitor failed: %s", exc)
        return {"agent_source": "THALOS", "monitored": False, "error": str(exc), "real_execution": False}


def run_automation_triggers(
    db: Session,
    user: Optional[User],
    pipeline: Dict[str, Any],
    payload: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Post-pipeline TeamFlow items visible in each agent workspace."""
    if not user:
        return []
    triggered: List[str] = []
    financial = pipeline.get("financial") or {}
    analysis = pipeline.get("analysis") or {}
    data = payload or pipeline.get("document", {}).get("data") or {}
    legal = data.get("legal_document") or (pipeline.get("document") or {}).get("legal_document") or {}
    employee = data.get("employee_name") or ""
    doc_id = legal.get("document_id")

    try:
        from services.teamflow_persistence_v1 import create_item

        base_content = {
            "document_id": doc_id,
            "employee_name": employee,
            "legal_document": legal,
            "analysis": analysis,
            "financial": financial,
            "trigger": "zeus_document_pipeline",
        }

        create_item(
            db,
            user,
            owner_agent="PERSEO",
            source_agent="AFRODITA",
            target_agent="PERSEO",
            title=f"Compliance — {employee or 'contrato RRHH'}",
            item_type="compliance_review",
            status="pending",
            content=base_content,
        )
        triggered.append("perseo.compliance_review")

        create_item(
            db,
            user,
            owner_agent="RAFAEL",
            source_agent="AFRODITA",
            target_agent="RAFAEL",
            title=f"Revisión fiscal — {employee or 'contrato RRHH'}",
            item_type="contract_fiscal_review",
            status="pending",
            content={
                **base_content,
                "invoice_required": bool(financial.get("invoice_required")),
                "estimated_value": financial.get("estimated_value"),
            },
        )
        triggered.append("rafael.contract_fiscal_review")

        create_item(
            db,
            user,
            owner_agent="THALOS",
            source_agent="AFRODITA",
            target_agent="THALOS",
            title=f"Monitor legal — {employee or 'contrato RRHH'}",
            item_type="contract_monitor",
            status="pending",
            content={**base_content, "thalos": pipeline.get("thalos")},
        )
        triggered.append("thalos.contract_monitor")

    except Exception as exc:
        logger.warning("[PIPELINE] teamflow items failed: %s", exc)

    if float(analysis.get("risk_score") or 0) >= HIGH_RISK_THRESHOLD:
        triggered.append("thalos.high_risk_alert")

    return triggered


def run_document_pipeline(
    db: Session,
    user: Optional[User],
    *,
    event_type: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Full PERSEO → RAFAEL → THALOS pipeline for document create events."""
    legal = payload.get("legal_document") or {}
    doc: Dict[str, Any] = {
        "type": "contract",
        "agent_source": payload.get("owner_agent") or "AFRODITA",
        "data": payload,
        "legal_document": legal,
    }

    analysis = analyze_document_perseo(doc)
    financial = process_financials_rafael(doc, payload)
    thalos = monitor_event_thalos(
        db,
        user,
        event_type,
        {"analysis": analysis, "financial": financial, "document_id": legal.get("document_id")},
    )

    result: Dict[str, Any] = {
        "event_type": event_type,
        "document": doc,
        "analysis": analysis,
        "financial": financial,
        "thalos": thalos,
        "real_execution": True,
    }
    result["automation_triggered"] = run_automation_triggers(db, user, result, payload=payload)
    return result


def pipeline_status() -> Dict[str, Any]:
    return {
        "active": True,
        "agents": ["PERSEO", "RAFAEL", "THALOS", "JUSTICIA"],
        "event_types": ["contract_rrhh_created", "document_signed", "invoice_generated"],
        "high_risk_threshold": HIGH_RISK_THRESHOLD,
    }
