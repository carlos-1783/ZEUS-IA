"""
💼 RAFAEL Automation Handler
Genera entregables contables y fiscales automáticos.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from app.models.agent_activity import AgentActivity
from .. import utils


def _build_invoice_template() -> Dict[str, Any]:
    return {
        "invoice_number": "INV-{{YYYY}}{{MM}}-001",
        "issue_date": "{{today}}",
        "customer": "{{client_name}}",
        "concept": "Suscripción ZEUS IA (Plan Autónomo)",
        "items": [
            {"description": "Implementación y configuración inicial", "price": 0, "tax": 21},
            {"description": "Licencia mensual ZEUS IA", "price": 0, "tax": 21},
        ],
        "notes": "Emisión automática sin coste inicial. Ajustar precio al activar plan comercial.",
    }


def _build_tax_models() -> Dict[str, Any]:
    quarter = (datetime.utcnow().month - 1) // 3 + 1
    return {
        "modelo_303": {
            "quarter": quarter,
            "required_fields": ["Base imponible", "Cuota soportada", "Cuota repercutida"],
            "status": "Plantilla preparada",
        },
        "modelo_390": {
            "year": datetime.utcnow().year,
            "notes": "Se rellenará automáticamente con los datos consolidados del año.",
        },
    }


def _build_cashflow_projection() -> Dict[str, Any]:
    return {
        "months": [
            {"month": "Mes 1", "expected_recurring": 0, "expected_expenses": 0, "notes": "Activación piloto sin coste."},
            {"month": "Mes 2", "expected_recurring": 950, "expected_expenses": 150, "notes": "Primeros clientes beta."},
            {"month": "Mes 3", "expected_recurring": 2400, "expected_expenses": 300, "notes": "Escalado con funnels automatizados."},
        ],
        "alerts": [
            "Configurar recordatorios automáticos para cobros pendientes.",
            "Sincronizar con Stripe para facturación inmediata al pasar a plan comercial.",
        ],
    }


def handle_rafael_task(activity: AgentActivity) -> Dict[str, Any]:
    agent = activity.agent_name.upper()
    prefix = f"{activity.id}_{activity.action_type}"

    deliverable = {
        "invoice_template": _build_invoice_template(),
        "tax_models": _build_tax_models(),
        "cashflow_projection": _build_cashflow_projection(),
        "summary": "Documentación fiscal y financiera preparada para activar facturación automática.",
    }

    json_path = utils.write_json(agent, prefix, deliverable, company_id=activity.company_id)
    markdown = utils.summarize_markdown(
        "Paquete Fiscal ZEUS IA",
        {
            "Resumen": deliverable["summary"],
            "Plantillas disponibles": [
                "Factura automática INV-{{YYYY}}{{MM}}-001",
                "Modelos 303 y 390 configurados con placeholders",
                "Proyección de tesorería trimestral",
            ],
            "Próximos pasos": [
                "Activar Stripe modo producción",
                "Registrar certificados digitales en Hacienda",
                "Sincronizar contabilidad con integraciones bancarias",
            ],
        },
    )
    markdown_path = utils.write_markdown(agent, prefix, markdown, company_id=activity.company_id)

    return {
        "status": "completed",
        "details_update": {
            "automation": {
                "deliverables": {"json": json_path, "markdown": markdown_path},
                "summary": deliverable["summary"],
            }
        },
        "metrics_update": {"templates_generated": 3},
        "notes": f"Paquete fiscal generado. Archivos disponibles en {json_path}",
    }

