"""Tareas estructuradas para orquestación ZEUS Core (intent → execution)."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ZeusIntentType = Literal[
    "unknown",
    "create_campaign_send",
    "list_customers_summary",
    "create_customer",
    "get_cashflow",
    "get_metrics",
    "confirm_pending",
    "analytics_summary",
    "tpv_sales_summary",
    "tpv_sales_today",
    "shift_status",
]


UrgencyType = Literal["low", "normal", "high"]


class ZeusEntities(BaseModel):
    """J8: entidades tipadas extraidas del mensaje. Solo se rellena lo que aparece de verdad."""

    names: List[str] = Field(default_factory=list)
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    # [{"value": 120.5, "currency": "EUR"}]
    amounts: List[Dict[str, Any]] = Field(default_factory=list)
    percentages: List[float] = Field(default_factory=list)
    # {"label": "today|yesterday|week|month|year|last_days|custom", "days": int}
    period: Optional[Dict[str, Any]] = None
    # Fechas explicitas normalizadas a ISO (YYYY-MM-DD)
    dates: List[str] = Field(default_factory=list)
    invoice_ids: List[str] = Field(default_factory=list)
    customer_ids: List[int] = Field(default_factory=list)
    # "all_customers" cuando el mensaje nombra destinatarios (clientes/todos/CRM); None si no.
    recipients: Optional[str] = None


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
    # J8: comprension estructurada (campos nuevos con valor por defecto: no rompen consumidores).
    entities: ZeusEntities = Field(default_factory=ZeusEntities)
    urgency: UrgencyType = "normal"
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    # Entidades obligatorias para la accion que faltan (p. ej. ["email"]).
    missing_entities: List[str] = Field(default_factory=list)
    # Intenciones que compiten con la elegida (ambiguedad).
    ambiguous_with: List[str] = Field(default_factory=list)
    # Desglose del calculo de confianza (auditable).
    confidence_breakdown: Dict[str, Any] = Field(default_factory=dict)


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
    # Empresa con la que realmente se ejecuto la accion (la rellena execute_action desde el
    # contexto de servidor). La usa la auditoria THALOS post-accion.
    company_id: Optional[int] = None
