"""
ZEUS data pipeline v1 — RRHH → OPS → WORKSPACE event chain via workspace playbooks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

PIPELINE_FLOW: List[str] = ["rrhh", "ops", "logistics", "workspace"]
NEXT_STAGE: Dict[str, Optional[str]] = {
    "rrhh": "ops",
    "ops": "logistics",
    "logistics": "workspace",
    "workspace": None,
}


def pipeline_definition() -> Dict[str, Any]:
    return {
        "version": "v1",
        "flow": ["RRHH", "OPS", "WORKSPACE"],
        "stages": PIPELINE_FLOW[:-1],
        "sink": "workspace_playbooks",
        "active": True,
    }


def attach_pipeline_metadata(stage: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    src = (stage or "").strip().lower()
    return {
        **payload,
        "zeus_pipeline": {
            "version": "v1",
            "stage": src,
            "flow": "RRHH→OPS→WORKSPACE",
            "next_stage": NEXT_STAGE.get(src),
        },
    }


def get_pipeline_status(db: Session, user_id: int) -> Dict[str, Any]:
    """Per-user pipeline progress from persisted workspace playbooks."""
    from app.models.workspace_playbook import WorkspacePlaybook

    rows = (
        db.query(WorkspacePlaybook.agent_source)
        .filter(
            WorkspacePlaybook.user_id == user_id,
            WorkspacePlaybook.agent_name == "AFRODITA",
        )
        .all()
    )
    sources = {str(r[0]).lower() for r in rows if r[0]}
    stages_completed = [s for s in PIPELINE_FLOW if s in sources or s == "workspace" and sources]
    return {
        **pipeline_definition(),
        "stages_completed": stages_completed,
        "playbook_sources": sorted(sources),
        "chain_closed": bool(sources & {"rrhh", "ops"}) or bool(sources & {"rrhh", "logistics"}),
    }
