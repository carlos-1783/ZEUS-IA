"""
Herramientas de workspace para JUSTICIA.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List

from .base import log_tool_execution


def sign_pdf_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Simular firma digital generando un hash seguro."""
    document_name = payload.get("document_name", "documento.pdf")
    digest = payload.get("file_hash", "")
    signer = payload.get("signer", "JUSTICIA")

    composite = f"{document_name}:{digest}:{signer}:{datetime.utcnow().isoformat()}"
    signature = hashlib.sha256(composite.encode("utf-8")).hexdigest()
    result = {
        "document": document_name,
        "signature": signature,
        "signed_at": datetime.utcnow().isoformat(),
        "signer": signer,
    }

    log_tool_execution("JUSTICIA", "pdf_signer", "Documento firmado digitalmente", {"payload": payload, "result": result})
    return result


def generate_contract_kit(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Generar contrato base con cláusulas esenciales."""
    parties = payload.get("parties", [])
    scope = payload.get("scope", "servicios")
    clauses = [
        "Objeto y alcance del servicio",
        "Condiciones económicas y calendario de pagos",
        "Confidencialidad y protección de datos",
        "Limitación de responsabilidad",
    ]
    if payload.get("media_buying"):
        clauses.append("Propiedad intelectual de creatividades / media.")

    result = {
        "parties": parties,
        "scope": scope,
        "clauses": clauses,
        "delivery_format": "markdown",
    }
    log_tool_execution("JUSTICIA", "contract_generator", "Contrato generado", {"payload": payload, "result": result})
    return result


def run_gdpr_audit(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Checklist rápido de cumplimiento GDPR."""
    systems: List[str] = payload.get("systems", [])
    flows: List[str] = payload.get("data_flows", [])

    issues = []
    if not flows:
        issues.append("Registrar flujos de datos entre agentes.")
    if "whatsapp" in systems:
        issues.append("Verificar consentimiento explícito para WhatsApp.")

    statuses = [
        {"system": system, "status": "ok" if system not in ("whatsapp", "crm") else "review"}
        for system in systems
    ]

    result = {
        "findings": issues or ["Cumplimiento validado sin observaciones críticas."],
        "systems": statuses,
    }
    log_tool_execution("JUSTICIA", "gdpr_audit", "GDPR auditado", {"payload": payload, "result": result})
    return result

