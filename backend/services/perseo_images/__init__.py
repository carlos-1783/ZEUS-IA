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

import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from fastapi import UploadFile

from app.core.config import settings

ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

UPLOAD_ROOT = Path(settings.PERSEO_IMAGE_UPLOAD_DIR).resolve()
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

MAX_BYTES = settings.PERSEO_IMAGE_MAX_BYTES


def _build_relative_path(filename: str) -> str:
    relative = Path("uploads") / "perseo" / filename
    return relative.as_posix()


def _build_public_url(relative_path: str) -> str:
    base = settings.STATIC_URL.rstrip("/") or "/static"
    return f"{base}/{relative_path.lstrip('/')}"


async def save_image(upload_file: UploadFile) -> Dict[str, Any]:
    """
    Guardar imagen subida por el usuario y devolver metadatos.
    """
    if upload_file.content_type not in ALLOWED_TYPES:
        raise ValueError(
            "Formato no soportado. Usa JPEG, PNG o WEBP."
        )

    extension = ALLOWED_TYPES[upload_file.content_type]
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    token = secrets.token_urlsafe(6)
    filename = f"perseo_{timestamp}_{token}{extension}"
    destination = UPLOAD_ROOT / filename

    size = 0
    try:
        with destination.open("wb") as buffer:
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError(
                        f"La imagen supera el límite de {MAX_BYTES // (1024 * 1024)}MB."
                    )
                buffer.write(chunk)
    except Exception:
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise
    finally:
        await upload_file.close()

    relative_path = _build_relative_path(filename)
    public_url = _build_public_url(relative_path)

    return {
        "filename": filename,
        "path": str(destination),
        "relative_path": relative_path,
        "url": public_url,
        "size_bytes": size,
        "content_type": upload_file.content_type,
        "storage": settings.IMAGE_STORAGE,
        "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
    }

