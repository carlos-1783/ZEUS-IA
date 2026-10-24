"""Interfaz estándar de acciones del orquestador ZEUS Core."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ZeusActionType = Literal[
    "unknown",
    "confirm_pending",
    "send_campaign",
    "list_customers",
    "create_customer",
    "get_cashflow",
    "get_metrics",
    "generate_invoice",
    "generate_model_303",
    "get_tax_summary",
    "track_leads",
    "analytics_summary",
    "tpv_sales_summary",
    "shift_status",
    # J9e: acciones reales de JUSTICIA/AFRODITA expuestas en el chat (mismos nombres que el ejecutor).
    "get_legal_status",
    "run_compliance_audit",
    "get_inventory_status",
    "get_security_status",  # Fase 2 / Step 3: THALOS
    "get_daily_close",  # Fase 2 / Step 1: RAFAEL
    "get_pending_invoices",  # Fase 2 / Step 1: RAFAEL
    "get_last_invoice",  # RAFAEL: ultima factura
    "get_invoices_today",  # RAFAEL: facturas de hoy
    "get_invoices_period",  # RAFAEL: facturas de ayer / esta semana / la pasada / este mes / el pasado
    "get_vat_quarter",  # RAFAEL: IVA del trimestre (ventas TPV, sin envio a la AEAT)
    "get_sales_performance",  # Fase 2 / Step 1: PERSEO
    "get_attendance_status",  # Fase 2 / Step 1: AFRODITA
    "get_today_agenda",  # Fase 2 / Step 1: AFRODITA
    "get_weekly_orders",  # Fase 2 / Step 1: AFRODITA (bloqueo honesto: no hay modelo de pedidos)
    "get_staff_schedule",  # AFRODITA: cuadrante semanal (empleados reales + horarios guardados)
    "review_contracts",  # Fase 2 / Step 1: JUSTICIA
    "get_coordination_report",  # Fase 2 / Step 1: ZEUS
    "create_ops_route",
    "create_inventory_movement",
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
