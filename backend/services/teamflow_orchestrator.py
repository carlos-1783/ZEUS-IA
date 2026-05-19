"""
Fachada TeamFlow → orquestador ZEUS Core (compatibilidad con imports existentes).
"""

from services.zeus_orchestrator_service import (
    AGENT_ZEUS,
    execute_action,
    try_handle_zeus_chat,
)

__all__ = ["try_handle_zeus_chat", "execute_action", "AGENT_ZEUS"]
