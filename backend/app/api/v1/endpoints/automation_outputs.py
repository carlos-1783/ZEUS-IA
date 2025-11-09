"""
📦 Automation Outputs Endpoints
Permite listar y descargar los entregables generados automáticamente.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from services.automation.utils import OUTPUT_BASE_DIR

router = APIRouter()


def _collect_outputs(agent: Optional[str] = None) -> List[Dict[str, str]]:
    base = OUTPUT_BASE_DIR
    if not base.exists():
        return []

    outputs: List[Dict[str, str]] = []
    agents = [agent.lower()] if agent else [p.name for p in base.iterdir() if p.is_dir()]

    for agent_name in agents:
        agent_dir = base / agent_name
        if not agent_dir.exists():
            continue
        for file in agent_dir.iterdir():
            if file.is_file():
                stat = file.stat()
                outputs.append(
                    {
                        "agent": agent_name.upper(),
                        "filename": file.name,
                        "path": f"{agent_name}/{file.name}",
                        "size_bytes": stat.st_size,
                        "created_at": stat.st_mtime,
                    }
                )

    outputs.sort(key=lambda item: item["created_at"], reverse=True)
    return outputs


@router.get("/outputs")
async def list_outputs(agent: Optional[str] = None):
    """
    Listar los entregables generados por los agentes.
    """
    files = _collect_outputs(agent)
    return {
        "success": True,
        "total": len(files),
        "outputs": files,
    }


@router.get("/outputs/{agent}/{filename}")
async def download_output(agent: str, filename: str):
    """
    Descargar un entregable concreto.
    """
    file_path = OUTPUT_BASE_DIR / agent.lower() / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(file_path)

