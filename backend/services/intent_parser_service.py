"""Intent parser + action builder para ZEUS Core."""

from __future__ import annotations

from typing import List, Optional

from app.models.user import User
from app.schemas.zeus_action import ZeusAction
from app.schemas.zeus_task import ZeusTaskObject
from services.intent_parser import is_confirmation_message, looks_like_operational, parse_intent
import services.crm_office_service as crm_svc

from sqlalchemy.orm import Session


def parse_message(message: str) -> ZeusTaskObject:
    return parse_intent(message)


def build_action(
    db: Session,
    user: User,
    task: ZeusTaskObject,
) -> ZeusAction:
    """Convierte intención detectada en ZeusAction con módulos y payload."""
    company_id = crm_svc.primary_company_id(db, user)
    modules = _modules_for_intent(task.intent)
    payload = {
        "discount_percent": task.discount_percent,
        "target": task.target,
        "campaign_name": task.campaign_name,
        "message_template": task.message_template,
        **(task.metadata or {}),
    }
    action_type = _map_intent_to_action_type(task.intent, task.action)
    return ZeusAction(
        action_type=action_type,
        company_id=company_id,
        user_id=user.id,
        payload=payload,
        modules=modules,
        requires_confirmation=task.requires_confirmation,
        confidence=task.confidence,
        raw_message=task.raw_message,
    )


def _map_intent_to_action_type(intent: str, legacy_action: Optional[str]) -> str:
    mapping = {
        "create_campaign_send": "send_campaign",
        "list_customers_summary": "list_customers",
        "confirm_pending": "confirm_pending",
        "analytics_summary": "analytics_summary",
        "tpv_sales_summary": "tpv_sales_summary",
        "tpv_sales_today": "tpv_sales_summary",
        "shift_status": "shift_status",
        "create_customer": "create_customer",
        "get_cashflow": "get_cashflow",
        "get_metrics": "get_metrics",
        "create_customer": "create_customer",
    }
    if intent in mapping:
        return mapping[intent]
    if legacy_action == "list_customers":
        return "list_customers"
    if legacy_action == "create_campaign":
        return "send_campaign"
    return "unknown"


def _modules_for_intent(intent: str) -> List[str]:
    if intent == "create_campaign_send":
        return ["crm_agent", "perseo_agent", "activity_log"]
    if intent == "list_customers_summary":
        return ["crm_agent", "activity_log"]
    if intent == "analytics_summary":
        return ["analytics_agent", "activity_log"]
    if intent == "tpv_sales_summary":
        return ["tpv", "activity_log"]
    if intent == "shift_status":
        return ["hr_agent", "activity_log"]
    if intent == "create_customer":
        return ["crm_agent", "activity_log"]
    if intent == "get_cashflow":
        return ["analytics", "activity_log"]
    if intent == "get_metrics":
        return ["analytics", "activity_log"]
    if intent == "confirm_pending":
        return ["activity_log"]
    return []


__all__ = [
    "parse_message",
    "build_action",
    "is_confirmation_message",
    "looks_like_operational",
    "parse_intent",
]
