"""
Herramientas de workspace para THALOS.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from .base import log_tool_execution

SUSPICIOUS_PATTERNS = ["DROP TABLE", "UNION SELECT", "failed login", "unauthorized"]


def monitor_security_logs(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Analizar logs y detectar anomalías simples."""
    logs: List[str] = payload.get("logs", [])
    alerts = []
    for line in logs:
        if any(pattern.lower() in line.lower() for pattern in SUSPICIOUS_PATTERNS):
            alerts.append({"line": line, "pattern": "detected"})

    result = {
        "total_lines": len(logs),
        "alerts": alerts,
        "recommendation": "Activar aislamiento automático" if alerts else "Sin hallazgos críticos",
    }
    log_tool_execution("THALOS", "log_monitor", "Logs verificados", {"result": result})
    return result


def detect_threat_events(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluar eventos y calcular riesgo agregado."""
    events: List[Dict[str, Any]] = payload.get("events", [])
    risk_score = 0
    normalized = []
    for event in events:
        severity = event.get("severity", 1)
        risk_score += severity
        normalized.append(
            {
                "source": event.get("source"),
                "severity": severity,
                "recommended_action": "aislar" if severity >= 3 else "monitorizar",
            }
        )

    result = {
        "risk_score": risk_score,
        "events": normalized,
        "status": "critical" if risk_score >= 6 else "ok",
    }
    log_tool_execution(
        "THALOS",
        "threat_detector",
        "Eventos de seguridad evaluados",
        {"payload": payload, "result": result},
        metrics={"risk_score": risk_score},
    )
    return result


def revoke_credentials(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Marcar credenciales como revocadas."""
    credentials: List[str] = payload.get("credential_ids", [])
    result = {
        "revoked": [
            {"credential_id": cred, "revoked_at": datetime.utcnow().isoformat()} for cred in credentials
        ],
        "count": len(credentials),
    }
    log_tool_execution("THALOS", "credential_revoker", "Credenciales revocadas", {"result": result})
    return result

