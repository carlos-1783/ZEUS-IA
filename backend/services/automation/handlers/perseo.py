"""
🎯 PERSEO Automation Handler
Genera entregables automáticos de marketing.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from app.models.agent_activity import AgentActivity
from .. import utils
# Importación diferida para evitar circular import


def _build_video_script(activity: AgentActivity) -> Dict[str, Any]:
    return {
        "title": "Lanzamiento ZEUS IA – Coste 0",
        "goal": "Presentar ZEUS IA como sistema autónomo que opera 24/7 sin personal.",
        "duration": "60 segundos",
        "structure": [
            {"segment": "Hook (0-5s)", "copy": "¿Tu negocio podría funcionar solo, sin empleados ni estrés?"},
            {"segment": "Problema (5-15s)", "copy": "Facturación, ventas y soporte consumen tu tiempo."},
            {"segment": "Solución (15-40s)", "copy": "ZEUS IA automatiza ventas, WhatsApp, contabilidad y seguridad."},
            {"segment": "Prueba (40-50s)", "copy": "Integrado con Stripe, Google, Hacienda y OpenAI."},
            {"segment": "CTA (50-60s)", "copy": "Activa ZEUS IA hoy y libera tu agenda. Entra a zeus-ia.com"},
        ],
        "visual_notes": [
            "Mostrar dashboard holográfico con agentes (ZEUS, PERSEO, RAFAEL, THALOS).",
            "Insertar testimonios breves con métricas de ahorro de tiempo.",
        ],
    }


def _build_ai_prompts() -> Dict[str, Any]:
    return {
        "video_generator": {
            "platform": "runwayml/gen-2",
            "prompt": "Futuristic business control room with holographic assistants orchestrating finance, marketing, and customer support tasks autonomously.",
        },
        "thumbnail": {
            "platform": "midjourney",
            "prompt": "High-tech AI control center with glowing interfaces, business metrics, and the title 'ZEUS IA' in bold.",
        },
        "voiceover": {
            "platform": "elevenlabs",
            "text": "ZEUS IA automatiza tu negocio las 24 horas. Desde ventas hasta finanzas y soporte, todo funciona solo. Actívalo hoy.",
        },
    }


def _build_distribution_plan() -> Dict[str, Any]:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return {
        "launch_date": today,
        "channels": {
            "linkedin": {
                "type": "Thought leadership post + vídeo nativo",
                "copy": [
                    "📢 Presentamos ZEUS IA: tu negocio funcionando en piloto automático.",
                    "Beneficios: venta automatizada, facturación sin errores, soporte inmediato.",
                ],
            },
            "instagram": {
                "assets": ["Teaser de 15s (Reel)", "Carrusel con 3 casos de uso"],
                "cta": "Link a landing con demo gratuita.",
            },
            "email": {
                "subject": "Tu negocio funcionando 24/7 sin personal, ¿listo?",
                "body_outline": ["Problema actual", "Solución ZEUS IA", "CTA: Solicita activación"],
            },
        },
        "automation": {
            "whatsapp": "Mensaje trigger a leads calientes con demo en vivo.",
            "crm_update": "Crear etapa 'Demo programada' y asignar manager virtual.",
        },
    }


def handle_perseo_task(activity: AgentActivity) -> Dict[str, Any]:
    agent = activity.agent_name.upper()
    prefix = f"{activity.id}_{activity.action_type}"

    details = activity.details or {}
    image_url = None
    if isinstance(details, dict):
        image_url = details.get("image_url")
        if not image_url:
            context_block = details.get("context") or details.get("payload")
            if isinstance(context_block, dict):
                image_url = context_block.get("image_url")

    deliverable = {
        "video_script": _build_video_script(activity),
        "ai_prompts": _build_ai_prompts(),
        "distribution_plan": _build_distribution_plan(),
        "summary": "Plan integral de lanzamiento listo para ejecutar con IA y canales orgánicos/pagos.",
    }

    artifact_id = utils.build_artifact_id(prefix)

    # Importación diferida para evitar circular import
    from services.video_service import generate_marketing_video
    if image_url:
        deliverable["reference_image_url"] = image_url
        visual_notes = deliverable["video_script"].setdefault("visual_notes", [])
        visual_notes.append(f"Imagen de referencia: {image_url}")
        video_prompt = deliverable["ai_prompts"].get("video_generator", {})
        if "prompt" in video_prompt:
            video_prompt["prompt"] = f"{video_prompt['prompt']}\nImagen de referencia: {image_url}"

    # Registrar inicio de generación como actividad visible
    from services.activity_logger import ActivityLogger as _AL
    _user_email = getattr(activity, "user_email", None)
    _AL.log_activity(
        agent_name="PERSEO",
        action_type="video_script_generated",
        action_description="Guion y plan de lanzamiento generados por PERSEO (vídeo + distribución multicanal)",
        details={
            "activity_id": activity.id,
            "action_type": activity.action_type,
            "channels": list(deliverable.get("distribution_plan", {}).get("channels", {}).keys()),
        },
        user_email=_user_email,
        status="in_progress",
        priority="normal",
        visible_to_client=True,
    )

    video_result = generate_marketing_video(deliverable, agent, prefix, artifact_id=artifact_id)
    video_path = (
        video_result.get("relative_path")
        if video_result.get("success")
        else None
    ) or video_result.get("path")
    deliverable["video_asset"] = video_result

    json_path = utils.write_json(agent, prefix, deliverable, artifact_id=artifact_id)
    markdown_content = utils.summarize_markdown(
        "Plan de Lanzamiento ZEUS IA",
        {
            "Resumen": [
                "Sistema 100% automatizado listo para presentarse como solución plug-and-play.",
                "Incluye guion, prompts de IA y plan de difusión multicanal.",
            ],
            "Guion de vídeo": [seg["copy"] for seg in deliverable["video_script"]["structure"]],
            "Prompts IA": [
                f"{platform}: "
                f"{info.get('prompt') or info.get('text')}"
                if isinstance(info, dict)
                else f"{platform}: {info}"
                for platform, info in deliverable["ai_prompts"].items()
            ],
            "Acciones de difusión": [
                "LinkedIn: contenido educativo + video nativo.",
                "Instagram: teaser + carrusel.",
                "Email: seguimiento a leads interesados.",
                "WhatsApp: secuencia automatizada para demos.",
            ],
            "Video generado": [
                (
                    f"Archivo disponible: {Path(video_path).name}"
                    if video_path
                    else "Se generó GIF de apoyo como fallback." if video_result.get("success")
                    else "Pendiente de generación (revisar dependencias MoviePy/FFmpeg)."
                )
            ],
        },
    )
    markdown_path = utils.write_markdown(agent, prefix, markdown_content, artifact_id=artifact_id)

    # Registrar resultado final en actividad visible al cliente
    _AL.log_activity(
        agent_name="PERSEO",
        action_type="marketing_plan_completed",
        action_description=(
            f"Plan de marketing completado: guion, prompts IA y distribución multicanal listos"
            + (f" | Vídeo generado: {Path(video_path).name}" if video_path else " | Vídeo pendiente")
        ),
        details={
            "activity_id": activity.id,
            "json_artifact": json_path,
            "markdown_artifact": markdown_path,
            "video_path": video_path,
            "video_success": bool(video_path),
        },
        metrics={
            "assets_generated": 3 + (1 if video_path else 0),
            "video_generated": 1 if video_path else 0,
        },
        user_email=_user_email,
        status="completed",
        priority="normal",
        visible_to_client=True,
    )

    return {
        "status": "completed",
        "details_update": {
            "automation": {
                "deliverables": {
                    "json": json_path,
                    "markdown": markdown_path,
                    "video": video_path,
                },
                "summary": deliverable["summary"],
                "video_asset": video_result,
                **({"image_url": image_url} if image_url else {}),
            }
        },
        "metrics_update": {
            "assets_generated": 3 + (1 if video_path else 0),
            "video_generated": 1 if video_path else 0,
        },
        "notes": (
            f"Plan de marketing generado automáticamente. Archivos: {json_path}"
            + (f" | Vídeo: {video_path}" if video_path else "")
        ),
    }

