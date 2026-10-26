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
            from app.db.rls_context import open_system_session
            from services.thalos_monitor_service import ingest_log_lines

            # Endpoint solo superusuario (workspaces.py): ingesta global de logs, system auditado.
            db = open_system_session("thalos_tools.monitor_security_logs (superusuario)")
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
        from app.db.rls_context import open_system_session
        from services.thalos_monitor_service import audit_from_db
        from services.thalos_threat_engine import evaluate_events

        # Endpoint solo superusuario (workspaces.py): motor de amenazas global, system auditado.
        db = open_system_session("thalos_tools.detect_threat_events (superusuario)")
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


CREDENTIAL_REVOKER_NOT_IMPLEMENTED = (
    "No hay almacen de credenciales revocables integrado (claves API de terceros, tokens de "
    "integraciones): THALOS no puede revocarlas. No se ha revocado nada; revocalas en el "
    "proveedor y rota la variable de entorno."
)


def revoke_credentials(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Fase 2 / Step 2: antes devolvia cada credential_id como "revocada" (con fecha) y
    real_execution=True sin revocar nada. Ahora informa de que no esta implementado."""
    credentials: List[str] = payload.get("credential_ids", [])
    result = {
        "revoked": [],
        "requested": list(credentials),
        "count": 0,
        "real_execution": False,
        "error": "credential_revoker_not_implemented",
        "message": CREDENTIAL_REVOKER_NOT_IMPLEMENTED,
    }
    log_tool_execution("THALOS", "credential_revoker", "Revocacion NO ejecutada (sin implementar)", {"result": result})
    return result
