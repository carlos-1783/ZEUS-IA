"""
🧰 Automation Utilities
Funciones auxiliares para generar archivos y manejar rutas
de los entregables automáticos.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


OUTPUT_BASE_DIR = Path(os.getenv("AGENT_OUTPUT_DIR", "storage/outputs")).resolve()
LOG_BASE_DIR = Path(os.getenv("AGENT_AUTOMATION_LOG_DIR", "backend/logs/automation")).resolve()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def build_artifact_id(prefix: str) -> str:
    """Generar un identificador único para los artefactos de un entregable."""
    return f"{prefix}_{timestamp()}"


def write_json(
    agent: str,
    prefix: str,
    payload: Dict[str, Any],
    base_dir: Path = OUTPUT_BASE_DIR,
    artifact_id: Optional[str] = None,
) -> str:
    """Persistir un archivo JSON y devolver su ruta absoluta."""
    agent_dir = ensure_dir(base_dir / agent.lower())
    base_name = artifact_id or build_artifact_id(prefix)
    file_path = agent_dir / f"{base_name}.json"
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return str(file_path.resolve())


def write_markdown(
    agent: str,
    prefix: str,
    content: str,
    base_dir: Path = OUTPUT_BASE_DIR,
    artifact_id: Optional[str] = None,
) -> str:
    """Persistir un archivo Markdown y devolver su ruta absoluta."""
    agent_dir = ensure_dir(base_dir / agent.lower())
    base_name = artifact_id or build_artifact_id(prefix)
    file_path = agent_dir / f"{base_name}.md"
    with file_path.open("w", encoding="utf-8") as handle:
        handle.write(content)
    return str(file_path.resolve())


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

