"""
🧰 Automation Utilities
Funciones auxiliares para generar archivos y manejar rutas
de los entregables automáticos.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)

LOG_BASE_DIR = Path(os.getenv("AGENT_AUTOMATION_LOG_DIR", "backend/logs/automation")).resolve()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def build_artifact_id(prefix: str) -> str:
    """Generar un identificador único para los artefactos de un entregable."""
    return f"{prefix}_{timestamp()}"


def output_url(agent: str, filename: str) -> str:
    """URL estable del entregable (la API filtra por empresa al servirlo)."""
    return f"/api/v1/automation/outputs/{agent.lower()}/{filename}"


def store_output(
    agent: str,
    filename: str,
    data: bytes,
    content_type: str,
    *,
    company_id: Optional[int],
    user_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Guarda un entregable de agente en R2 (empresa/{id}/outputs/...).

    Fase 2 / Step 1: antes se escribia en storage/outputs (disco efimero) y la API lo
    listaba a TODAS las empresas. Sin empresa no se guarda fichero (el resultado sigue en
    la BD, en los detalles de la actividad) y se devuelve None: nunca a disco local.
    Sin R2 configurado tampoco: aviso en log y None (el entregable queda en BD)."""
    from app.db.rls_context import open_tenant_session
    from services import object_storage

    if not isinstance(company_id, int):
        logger.warning("entregable %s/%s sin empresa: no se guarda fichero", agent, filename)
        return None
    if not object_storage.is_configured():
        logger.warning(
            "entregable %s/%s no guardado como fichero: R2 sin configurar (%s)",
            agent, filename, ", ".join(object_storage.missing_config()),
        )
        return None
    db = open_tenant_session(company_id, user_id=user_id)  # RLS: solo la empresa del entregable
    try:
        row = object_storage.store_file(
            db,
            company_id=company_id,
            user_id=user_id,
            category="outputs",
            filename=filename,
            content_type=content_type,
            data=data,
            agent_name=agent,
        )
        return {
            "file_id": row.id,
            "filename": row.original_filename,
            "url": object_storage.file_url(row),
            "download_path": output_url(agent, row.original_filename),
            "size_bytes": row.size_bytes,
        }
    finally:
        db.close()


def write_json(
    agent: str,
    prefix: str,
    payload: Dict[str, Any],
    artifact_id: Optional[str] = None,
    *,
    company_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> Optional[str]:
    """Persistir un JSON de entregable en R2; devuelve su URL de descarga (o None sin empresa)."""
    base_name = artifact_id or build_artifact_id(prefix)
    data = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    stored = store_output(
        agent, f"{base_name}.json", data, "application/json", company_id=company_id, user_id=user_id
    )
    return stored["download_path"] if stored else None


def write_markdown(
    agent: str,
    prefix: str,
    content: str,
    artifact_id: Optional[str] = None,
    *,
    company_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> Optional[str]:
    """Persistir un Markdown de entregable en R2; devuelve su URL de descarga (o None)."""
    base_name = artifact_id or build_artifact_id(prefix)
    stored = store_output(
        agent, f"{base_name}.md", content.encode("utf-8"), "text/markdown",
        company_id=company_id, user_id=user_id,
    )
    return stored["download_path"] if stored else None


def write_log(agent: str, prefix: str, payload: Dict[str, Any]) -> str:
    """Guardar logs internos en la carpeta de automatización."""
    agent_dir = ensure_dir(LOG_BASE_DIR / agent.lower())
    filename = f"{prefix}_{timestamp()}.json"
    file_path = agent_dir / filename
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return str(file_path.resolve())


def merge_dict(base: Optional[Dict[str, Any]], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base or {})
    merged.update(updates)
    return merged


def summarize_markdown(title: str, sections: Dict[str, Any]) -> str:
    """Generar un documento Markdown simple a partir de un diccionario."""
    lines = [f"# {title}", ""]
    for heading, content in sections.items():
        lines.append(f"## {heading}")
        if isinstance(content, list):
            for item in content:
                lines.append(f"- {item}")
        elif isinstance(content, dict):
            for key, value in content.items():
                if isinstance(value, list):
                    lines.append(f"- **{key}:**")
                    for v in value:
                        lines.append(f"  - {v}")
                else:
                    lines.append(f"- **{key}:** {value}")
        else:
            lines.append(str(content))
        lines.append("")
    return "\n".join(lines).strip() + "\n"

