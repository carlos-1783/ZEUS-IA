"""
🔧 Workspace Tools Base Utilities
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from services.activity_logger import ActivityLogger


def log_tool_execution(
    agent: str,
    tool_name: str,
    description: str,
    details: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> None:
    """Registrar el uso de una herramienta de workspace."""
    ActivityLogger.log_activity(
        agent_name=agent.upper(),
        action_type=f"workspace_tool:{tool_name}",
        action_description=description,
        details=details,
        metrics=metrics,
        status="completed",
        priority="normal",
        visible_to_client=False,
    )

