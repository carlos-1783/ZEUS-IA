from __future__ import annotations

"""
{
  "task": "upgrade_zeus_full_stack",
  "description": "Configurar y completar TODOS los agentes de ZEUS IA sin sobrescribir prompts existentes. Solo agregar lo que falta, crear herramientas reales para los workspaces y dejar la arquitectura 100% operativa.",
  "mode": "safe_patch",
  "overwrite": false,
  "dry_run": false,
  "goals": [
    "No sobrescribir prompts ni configuraciones existentes.",
    "Añadir SOLO lo que falta en cada agente.",
    "Activar y conectar workspaces reales.",
    "Estructurar flujos entre agentes.",
    "Dejar ZEUS listo para operar sin intervención humana."
  ],

  "agents": {
    "ZEUS_CORE": {
      "add_capabilities": [
        "motor_de_orquestacion_teamflow",
        "coordinacion_multiagente",
        "decision_metadata",
        "context_sharing_entre_agentes",
        "validacion_legal_y_riesgos_con_auto_HITL",
        "panel_de_control_de_ejecuciones"
      ]
    },

    "PERSEO": {
      "add_capabilities": [
        "procesamiento_de_multiples_imagenes",
        "mejora_de_videos_existentes",
        "creacion_de_assets_para_ads",
        "SEO_tecnico_auditoria",
        "keyword_research",
        "integracion_con_Justicia_para_contratos",
        "integracion_con_Rafael_para_facturas"
      ],
      "workspace": {
        "tools": [
          "image_analyzer",
          "video_enhancer",
          "seo_audit_engine",
          "ads_campaign_builder"
        ]
      }
    },

    "RAFAEL": {
      "add_capabilities": [
        "lectura_QR",
        "lectura_NFC",
        "lectura_DNIe",
        "reconocimiento_superusuario",
        "modo_pre_lanzamiento_para_datos_incompletos"
      ],
      "workspace": {
        "tools": [
          "qr_reader",
          "nfc_scanner",
          "dni_ocr_parser",
          "fiscal_forms_generator"
        ]
      }
    },

    "JUSTICIA": {
      "add_capabilities": [
        "firma_digital_de_documentos",
        "generacion_y_firma_PDF",
        "integracion_con_Perseo_para_contratos_publicitarios",
        "integracion_con_Rafael_para_facturas",
        "auditoria_GDPR_en_tiempo_real"
      ],
      "workspace": {
        "tools": [
          "pdf_signer",
          "contract_generator",
          "gdpr_audit"
        ]
      }
    },

    "THALOS": {
      "add_capabilities": [
        "deteccion_temprana_anomalias",
        "aislamiento_automático",
        "proteccion_de_endpoints",
        "proteccion_CORS_y_API_gateway"
      ],
      "workspace": {
        "tools": [
          "log_monitor",
          "threat_detector",
          "credential_revoker"
        ]
      }
    },

    "AFRODITA": {
      "add_capabilities": [
        "fichaje_por_foto",
        "fichaje_por_QR",
        "fichaje_por_codigo",
        "gestion_turnos",
        "gestion_ausencias",
        "onboarding_empleados"
      ],
      "workspace": {
        "tools": [
          "face_check_in",
          "qr_check_in",
          "employee_manager",
          "contract_creator_rrhh"
        ]
      }
    }
  },

  "teamflow_engine": {
    "create": true,
    "workflows": [
      "prelaunch_campaign_v1",
      "invoice_flow_v1",
      "contract_sign_v1",
      "rrhh_onboarding_v1",
      "ads_launch_v1"
    ],
    "connect_agents": true,
    "validate_integrations": true
  },

  "system_integration": {
    "frontend_workspace_activation": true,
    "backend_api_enable_agent_tools": true,
    "cors_fix": true,
    "enable_uploads": ["imagenes", "videos", "documentos"],
    "enable_agent_to_agent_calls": true
  },

  "expected_result": "Todos los agentes de ZEUS IA quedan completados, con workspaces funcionales y herramientas reales, conectados entre sí mediante TeamFlow, sin sobrescribir nada, y dejándolo operativo al 100%."
}
"""
"""
📁 PERSEO Image Utilities
Servicio minimalista para almacenar imágenes de referencia de campañas.
"""

from typing import Any, Dict

from fastapi import UploadFile

from app.core.config import settings

ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

MAX_BYTES = settings.PERSEO_IMAGE_MAX_BYTES


async def save_image(db, user, upload_file: UploadFile) -> Dict[str, Any]:
    """
    Guardar la imagen de referencia de PERSEO en R2 (empresa/{id}/images/...).
    Fase 2 / Step 1: antes iba a STATIC_DIR/uploads/perseo y se servia sin autenticacion.
    """
    from services.upload_intake import store_upload

    try:
        stored = await store_upload(
            db,
            user,
            upload_file,
            category="images",
            allowed_types=frozenset(ALLOWED_TYPES),
            max_bytes=MAX_BYTES,
        )
    finally:
        await upload_file.close()
    return {
        "file_id": stored["file_id"],
        "filename": stored["filename"],
        "url": stored["url"],
        "size_bytes": stored["size_bytes"],
        "content_type": stored["content_type"],
        "storage": "r2",
    }
