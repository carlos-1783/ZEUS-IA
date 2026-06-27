"""Heuristic fallbacks for JUSTICIA tools."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import log_tool_execution


def generate_contract_heuristic(payload: Dict[str, Any]) -> Dict[str, Any]:
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
    result = {"parties": parties, "scope": scope, "clauses": clauses, "real_execution": False}
    log_tool_execution("JUSTICIA", "contract_generator", "Contrato heurístico", {"result": result})
    return result


def run_gdpr_heuristic(payload: Dict[str, Any]) -> Dict[str, Any]:
    systems: List[str] = payload.get("systems", [])
    flows: List[str] = payload.get("data_flows", [])
    issues = []
    if not flows:
        issues.append("Registrar flujos de datos entre agentes.")
    if "whatsapp" in systems:
        issues.append("Verificar consentimiento explícito para WhatsApp.")
    result = {
        "findings": issues or ["Sin observaciones (heurístico)"],
        "real_execution": False,
    }
    log_tool_execution("JUSTICIA", "gdpr_audit", "GDPR heurístico", {"result": result})
    return result
