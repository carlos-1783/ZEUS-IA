"""
System visibility v1 — flags Railway + estado por agente (Phase A).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal

from app.core.config import settings
from config.afrodita_flags_v1 import get_afrodita_safety_flags
from services.execution_mode_v1 import normalize_execution_mode

AgentStatusLabel = Literal["REAL", "PARTIAL", "FAKE", "DISCONNECTED"]

SYSTEM_STATE = "CONTROLLED_UNTRUSTED"
SYSTEM_STATE_ORCHESTRATION = "ORCHESTRATION_ACTIVE"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "yes", "on")


def _railway_flags() -> Dict[str, bool]:
    afrodita = get_afrodita_safety_flags()
    return {
        "AFRODITA_EXECUTION_ENABLED": bool(afrodita["AFRODITA_EXECUTION_ENABLED"]),
        "AFRODITA_READ_ONLY_MODE": bool(afrodita["AFRODITA_READ_ONLY_MODE"]),
        "AFRODITA_OPS_WRITES": bool(afrodita["writes_enabled"]),
        "AFRODITA_ENABLE_STOCK_SYNC": bool(getattr(settings, "AFRODITA_ENABLE_STOCK_SYNC", False)),
        "THALOS_EXECUTION_ENABLED": bool(getattr(settings, "THALOS_EXECUTION_ENABLED", False)),
        "THALOS_REAL_LOGS_ENABLED": bool(getattr(settings, "THALOS_REAL_LOGS_ENABLED", False)),
        "THALOS_BACKUP_ENABLED": bool(getattr(settings, "THALOS_BACKUP_ENABLED", False)),
        "JUSTICE_REAL_AUDIT_ENABLED": bool(getattr(settings, "JUSTICE_REAL_AUDIT_ENABLED", False)),
        "JUSTICE_READ_ONLY_MODE": bool(getattr(settings, "JUSTICE_READ_ONLY_MODE", True)),
        "ZEUS_CORE_ENABLED": bool(getattr(settings, "ZEUS_CORE_ENABLED", False)),
        "ZEUS_AGENT_ENABLED": bool(getattr(settings, "ZEUS_AGENT_ENABLED", True)),
        "RAFAEL_EXECUTION_ENABLED": _env_bool("RAFAEL_EXECUTION_ENABLED", False),
        "ZEUS_EVENT_BUS_ENABLED": _env_bool("ZEUS_EVENT_BUS_ENABLED", True),
        "ZEUS_AUTOMATION_ENGINE_ENABLED": _env_bool("ZEUS_AUTOMATION_ENGINE_ENABLED", False),
    }


def _afrodita_execution_mode(flags: Dict[str, bool]) -> str:
    if flags["AFRODITA_EXECUTION_ENABLED"] and not flags["AFRODITA_READ_ONLY_MODE"]:
        return "REAL"
    if flags["AFRODITA_READ_ONLY_MODE"]:
        return "READ_ONLY"
    return "SIMULATED"


def _thalos_execution_mode(flags: Dict[str, bool]) -> str:
    if flags["THALOS_EXECUTION_ENABLED"]:
        return "REAL"
    return "READ_ONLY"


def _justicia_execution_mode(flags: Dict[str, bool]) -> str:
    if flags["JUSTICE_REAL_AUDIT_ENABLED"]:
        return "REAL"
    if flags["JUSTICE_READ_ONLY_MODE"]:
        return "READ_ONLY"
    return "SIMULATED"


def _zeus_core_agent(flags: Dict[str, bool]) -> Dict[str, Any]:
    from services.zeus_core_orchestrator_v1 import check_core_orchestration_env

    orch = check_core_orchestration_env()
    base: Dict[str, Any] = {
        "name": "ZEUS CORE",
        "api_prefix": "/api/v1/zeus-core",
        "orchestration_active": orch["all_ok"],
    }
    if orch["all_ok"]:
        return {
            **base,
            "status": "REAL",
            "execution_mode": "REAL",
            "execution_ready": True,
            "notes": (
                "Orquestación multi-agente activa "
                "(payment_due → RAFAEL/AFRODITA/JUSTICIA/THALOS + auditoría)"
            ),
        }
    if flags.get("ZEUS_CORE_ENABLED") and flags.get("ZEUS_AGENT_ENABLED"):
        missing = [name for name, meta in orch["flags"].items() if not meta.get("ok")]
        return {
            **base,
            "status": "PARTIAL",
            "execution_mode": "REAL",
            "execution_ready": False,
            "notes": (
                "CORE habilitado — completar flags: " + ", ".join(missing)
                if missing
                else "CORE habilitado — revisar orquestación"
            ),
        }
    return {
        **base,
        "status": "DISCONNECTED",
        "execution_mode": "SIMULATED",
        "execution_ready": False,
        "notes": "Activar ZEUS_CORE_ENABLED + ZEUS_AGENT_ENABLED para orquestación real",
    }


def _agent_catalog(flags: Dict[str, bool]) -> List[Dict[str, Any]]:
    afrodita_mode = _afrodita_execution_mode(flags)
    afrodita_status: AgentStatusLabel = (
        "REAL" if afrodita_mode == "REAL" else "PARTIAL"
    )
    return [
        {
            "name": "AFRODITA",
            "status": afrodita_status,
            "execution_mode": afrodita_mode,
            "execution_ready": afrodita_mode == "REAL",
            "api_prefix": "/api/v1/afrodita/rrhh/v1",
            "notes": "RRHH/OPS con BD; escritura gated por flags",
        },
        {
            "name": "RAFAEL",
            "status": "PARTIAL",
            "execution_mode": "REAL",
            "execution_ready": False,
            "api_prefix": "/api/v1/scan",
            "notes": "Scan/fiscal persiste; chat LLM sin side-effects",
        },
        {
            "name": "THALOS",
            "status": "PARTIAL",
            "execution_mode": _thalos_execution_mode(flags),
            "execution_ready": False,
            "api_prefix": "/api/v1/thalos/v1",
            "notes": "v1 monitor real; legacy log-monitor = SIMULADO",
        },
        {
            "name": "JUSTICIA",
            "status": "PARTIAL",
            "execution_mode": _justicia_execution_mode(flags),
            "execution_ready": False,
            "api_prefix": "/api/v1/justicia/v1",
            "notes": "system-audit read-only; toolkit legal = stub",
        },
        {
            "name": "PERSEO",
            "status": "PARTIAL",
            "execution_mode": "REAL" if flags.get("AFRODITA_EXECUTION_ENABLED") else "SIMULATED",
            "execution_ready": bool(flags.get("AFRODITA_EXECUTION_ENABLED")),
            "api_prefix": "/api/v1/perseo",
            "notes": "LLM chat REAL; tools heurísticos SIMULATED; video edit REAL con FFmpeg",
        },
        _zeus_core_agent(flags),
    ]


def execution_status_payload() -> Dict[str, Any]:
    flags = _railway_flags()
    agents = _agent_catalog(flags)
    zeus_core_active = False
    for agent in agents:
        agent["execution_mode"] = normalize_execution_mode(agent["execution_mode"])
        agent["execution_ready"] = agent["status"] == "REAL" and agent["execution_mode"] == "REAL"
        if agent.get("name") == "ZEUS CORE" and agent.get("execution_ready"):
            zeus_core_active = True

    return {
        "phase": "C" if zeus_core_active else "A",
        "system_id": "system_visibility_and_cleanup_v1",
        "system_state": SYSTEM_STATE_ORCHESTRATION if zeus_core_active else SYSTEM_STATE,
        "visibility": "FULL",
        "fake_components": "EXPLICIT",
        "ready_for_flags_activation": not zeus_core_active,
        "zeus_core_orchestration_active": zeus_core_active,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "flags": flags,
        "agents": agents,
        "summary": {
            "execution_ready_count": sum(1 for a in agents if a["execution_ready"]),
            "partial_count": sum(1 for a in agents if a["status"] == "PARTIAL"),
            "fake_count": sum(1 for a in agents if a["status"] == "FAKE"),
        },
    }
