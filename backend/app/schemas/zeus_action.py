"""Interfaz estándar de acciones del orquestador ZEUS Core."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ZeusActionType = Literal[
    "unknown",
    "confirm_pending",
    "send_campaign",
    "list_customers",
    "analytics_summary",
    "tpv_sales_summary",
    "shift_status",
]

ZeusModuleName = Literal[
    "crm",
    "marketing",
    "tpv",
    "control_horario",
    "analytics",
    "activity_log",
    "notifications",
]


class ZeusAction(BaseModel):
    """Acción estructurada: intent → action → ejecución multi-módulo."""

    action_type: ZeusActionType = "unknown"
    company_id: Optional[int] = None
    user_id: int
    payload: Dict[str, Any] = Field(default_factory=dict)
    modules: List[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    confidence: float = 0.0
    raw_message: str = ""
