"""Thin writer hooks — persist playbooks after AFRODITA domain execution."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace_playbook import WorkspacePlaybook
from services.workspace_playbook_service_v1 import persist_execution_playbook


def write_rrhh_playbook(
    db: Session,
    user: User,
    *,
    action: str,
    title: str,
    payload: Dict[str, Any],
) -> Optional[WorkspacePlaybook]:
    return persist_execution_playbook(
        db, user, agent_source="rrhh", action=action, title=title, payload=payload
    )


def write_ops_playbook(
    db: Session,
    user: User,
    *,
    action: str,
    title: str,
    payload: Dict[str, Any],
) -> Optional[WorkspacePlaybook]:
    return persist_execution_playbook(
        db, user, agent_source="ops", action=action, title=title, payload=payload
    )


def write_logistics_playbook(
    db: Session,
    user: User,
    *,
    action: str,
    title: str,
    payload: Dict[str, Any],
) -> Optional[WorkspacePlaybook]:
    return persist_execution_playbook(
        db, user, agent_source="logistics", action=action, title=title, payload=payload
    )
