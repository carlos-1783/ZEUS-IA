"""
⚖️ JUSTICIA Automation Handler
Genera entregables legales y de cumplimiento.
"""

from __future__ import annotations

from typing import Dict, Any

from app.models.agent_activity import AgentActivity
from .. import utils


def _privacy_policy() -> str:
    return (
        "ZEUS IA recopila datos estrictamente necesarios para automatizar operaciones. "
        "Los datos se cifran en reposo y en tránsito. Los clientes pueden solicitar acceso, rectificación y "
        "eliminación en cualquier momento enviando un mensaje a privacidad@zeus-ia.com."
    )


def _terms_of_service() -> str:
    return (
        "Al activar ZEUS IA aceptas que el sistema orquestará procesos automatizados en ventas, soporte y finanzas. "
        "El cliente es responsable de proporcionar credenciales válidas y mantener la información fiscal actualizada."
    )


def _compliance_checklist() -> Dict[str, Any]:
    return {
        "gdpr": ["Contrato de encargado firmado", "Registro de tratamientos actualizado", "DPIA aprobada"],
        "integraciones": {
            "google": "OAuth2 con scopes mínimos firmada.",
            "stripe": "Webhooks firmados y logs auditados.",
            "whatsapp": "Sandbox y documentación de consentimiento almacenada.",
        },
        "alerts": ["Rotar credenciales cada 90 días", "Registrar logs de acceso a información sensible"],
    }


def handle_justicia_task(activity: AgentActivity) -> Dict[str, Any]:
    agent = activity.agent_name.upper()
    prefix = f"{activity.id}_{activity.action_type}"

    deliverable = {
        "privacy_policy": _privacy_policy(),
        "terms_of_service": _terms_of_service(),
        "compliance_checklist": _compliance_checklist(),
        "summary": "Documentación legal base preparada para prelanzamiento y auditoría RGPD.",
    }

    json_path = utils.write_json(agent, prefix, deliverable)
    markdown = utils.summarize_markdown(
        "Documentación Legal ZEUS IA",
        {
            "Política de Privacidad": deliverable["privacy_policy"],
            "Términos de Servicio": deliverable["terms_of_service"],
            "Checklist de Cumplimiento": [
                "GDPR: contrato encargado, registro de tratamientos y DPIA.",
                "Integraciones: Google, Stripe y WhatsApp auditadas.",
                "Alertas: rotación de credenciales y logs de accesos.",
            ],
        },
    )
    markdown_path = utils.write_markdown(agent, prefix, markdown)

    return {
        "status": "completed",
        "details_update": {
            "automation": {
                "deliverables": {"json": json_path, "markdown": markdown_path},
                "summary": deliverable["summary"],
            }
        },
        "metrics_update": {"docs_generated": 3},
        "notes": f"Kit legal generado y listo para revisión. Archivos: {json_path}",
    }

