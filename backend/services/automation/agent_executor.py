"""
🤖 Agent Automation Executor
Se encarga de revisar actividades pendientes de los agentes y resolverlas automáticamente.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Dict, Optional

from app.db.session import SessionLocal
from app.models.agent_activity import AgentActivity
from services.activity_logger import ActivityLogger

from .utils import merge_dict


AUTOMATION_ENABLED = os.getenv("AGENT_AUTOMATION_ENABLED", "true").lower() == "true"
AUTOMATION_INTERVAL = int(os.getenv("AGENT_AUTOMATION_INTERVAL", "600"))


class AgentAutomationExecutor:
    """Ejecutor centralizado de automatizaciones."""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if not AUTOMATION_ENABLED:
            print("[AUTOMATION] Deshabilitado por variable AGENT_AUTOMATION_ENABLED.")
            return

        if self._task and not self._task.done():
            return

        self._running = True
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._runner())
        print(f"[AUTOMATION] Executor iniciado (intervalo {AUTOMATION_INTERVAL}s).")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            print("[AUTOMATION] Executor detenido.")

    async def _runner(self) -> None:
        while self._running:
            try:
                await asyncio.to_thread(self._process_cycle)
            except Exception as exc:  # pylint: disable=broad-except
                print(f"[AUTOMATION] Error en ciclo: {exc}")
            await asyncio.sleep(AUTOMATION_INTERVAL)

    def _process_cycle(self) -> None:
        session = SessionLocal()
        try:
            pending = (
                session.query(AgentActivity)
                .filter(AgentActivity.status.in_(["pending", "in_progress"]))
                .order_by(AgentActivity.created_at.asc())
                .all()
            )

            if not pending:
                return

            for activity in pending:
                self._handle_activity(session, activity)
        finally:
            session.close()

    def _handle_activity(self, session, activity: AgentActivity) -> None:
        from services.unified_agent_runtime import run_workspace_task

        result = run_workspace_task(activity)
        agent = (activity.agent_name or "").upper()
        status = result.get("status", "completed")

        activity.status = status
        if status in ("completed", "executed_internal", "failed"):
            activity.completed_at = datetime.utcnow()
        elif status == "blocked_missing_handler":
            activity.completed_at = None

        if "details_update" in result:
            activity.details = merge_dict(activity.details, result["details_update"])

        if "metrics_update" in result:
            activity.metrics = merge_dict(activity.metrics, result["metrics_update"])

        executed_handler = result.get("executed_handler")
        if executed_handler is not None:
            activity.metrics = merge_dict(activity.metrics or {}, {"executed_handler": executed_handler})

        note = result.get("notes")
        session.add(activity)
        session.commit()

        if status == "blocked_missing_handler":
            ActivityLogger.log_activity(
                agent_name=agent,
                action_type="automation_blocked",
                action_description=f"Actividad bloqueada: sin handler para ({agent}, {activity.action_type}).",
                details={
                    "original_activity_id": activity.id,
                    "automation_status": status,
                    "note": note,
                },
                metrics=result.get("metrics_update"),
                status=status,
                priority=activity.priority,
            )
        else:
            ActivityLogger.log_activity(
                agent_name=agent,
                action_type="automation_update",
                action_description=f"Tarea '{activity.action_description}' atendida.",
                details={
                    "original_activity_id": activity.id,
                    "automation_status": status,
                    "executed_handler": executed_handler,
                    "note": note,
                },
                metrics=result.get("metrics_update"),
                status=status,
                priority=activity.priority,
            )


_executor = AgentAutomationExecutor()


async def start_agent_automation() -> None:
    await _executor.start()


async def stop_agent_automation() -> None:
    await _executor.stop()

