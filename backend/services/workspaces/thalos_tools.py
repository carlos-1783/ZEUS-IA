"""
Herramientas de workspace para THALOS — persistencia real en BD cuando THALOS_ENABLED.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import log_tool_execution


def monitor_security_logs(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Analizar logs reales → thalos_events + alertas."""
    logs: List[str] = payload.get("logs", [])
    try:
        from app.core.config import settings

        if getattr(settings, "THALOS_ENABLED", True) and logs:
            from app.db.session import SessionLocal
            from services.thalos_monitor_service import ingest_log_lines

            db = SessionLocal()
            try:
                result = ingest_log_lines(db, logs, source="workspace_tools")
                db.commit()
                log_tool_execution("THALOS", "log_monitor", "Logs persistidos en BD", {"result": result})
                return {**result, "ai_powered": False, "real_execution": True, "data_origin": "database"}
            finally:
                db.close()
    except Exception as exc:
        print(f"[THALOS][log_monitor] real ingest failed: {exc}")

    alerts = []
    for line in logs:
        lower = line.lower()
        if any(p in lower for p in ("failed login", "unauthorized", "drop table")):
            alerts.append({"line": line, "pattern": "detected"})
    result = {
        "total_lines": len(logs),
        "alerts": alerts,
        "recommendation": "Activar THALOS_REAL_LOGS_ENABLED para persistencia BD",
        "real_execution": False,
    }
    log_tool_execution("THALOS", "log_monitor", "Logs verificados (sin BD)", {"result": result})
    return result


def detect_threat_events(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluar eventos desde BD."""
    try:
        from app.db.session import SessionLocal
        from services.thalos_monitor_service import audit_from_db
        from services.thalos_threat_engine import evaluate_events

        db = SessionLocal()
        try:
            candidates = evaluate_events(db)
            audit = audit_from_db(db)
            result = {
                "risk_score": len(candidates) * 2,
                "candidates": candidates,
                "status": "critical" if any(c.get("level") == "critical" for c in candidates) else "ok",
                "database": audit,
                "real_execution": True,
            }
            log_tool_execution("THALOS", "threat_detector", "Threat engine evaluado", {"result": result})
            return result
        finally:
            db.close()
    except Exception as exc:
        print(f"[THALOS][threat] {exc}")

    events: List[Dict[str, Any]] = payload.get("events", [])
    risk_score = sum(int(e.get("severity", 1)) for e in events)
    return {
        "risk_score": risk_score,
        "events": events,
        "status": "critical" if risk_score >= 6 else "ok",
        "real_execution": False,
    }


def revoke_credentials(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Marcar credenciales — requiere THALOS_EXECUTION_ENABLED."""
    from datetime import datetime, timezone

    credentials: List[str] = payload.get("credential_ids", [])
    result = {
        "revoked": [
            {"credential_id": cred, "revoked_at": datetime.now(timezone.utc).isoformat()} for cred in credentials
        ],
        "count": len(credentials),
        "real_execution": bool(credentials),
    }
    log_tool_execution("THALOS", "credential_revoker", "Credenciales revocadas", {"result": result})
    return result
