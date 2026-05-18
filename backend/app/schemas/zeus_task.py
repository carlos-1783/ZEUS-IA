"""Tareas estructuradas para orquestación ZEUS Core (intent → execution)."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ZeusIntentType = Literal[
    "unknown",
    "create_campaign_send",
    "list_customers_summary",
    "confirm_pending",
]


class ZeusTaskObject(BaseModel):
    """Acción estructurada derivada del mensaje del usuario."""

    intent: ZeusIntentType = "unknown"
    action: Optional[str] = None
    discount_percent: Optional[float] = None
    target: str = "all_customers"
    campaign_name: Optional[str] = None
    message_template: Optional[str] = None
    requires_confirmation: bool = False
    raw_message: str = ""
    confidence: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ZeusExecutionStepResult(BaseModel):
    agent: str
    step: str
    success: bool
    detail: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)


class ZeusExecutionResult(BaseModel):
    success: bool
    intent: ZeusIntentType
    message: str
    executed: bool = False
    needs_confirmation: bool = False
    steps: List[ZeusExecutionStepResult] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
