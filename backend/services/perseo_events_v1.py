"""PERSEO realtime events — WebSocket push for job progress."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_main_loop: Optional[asyncio.AbstractEventLoop] = None


def register_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def emit_perseo_event(user_id: int, event: str, data: Dict[str, Any]) -> None:
    """Thread-safe emit from sync workers."""
    if not user_id:
        return
    payload = {"type": event, "source": "PERSEO", **data}
    try:
        from app.api.v1.endpoints.websocket import manager

        async def _send() -> None:
            await manager.send_user_json(user_id, payload)

        loop = _main_loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(_send(), loop)
        else:
            try:
                running = asyncio.get_running_loop()
                running.create_task(_send())
            except RuntimeError:
                asyncio.run(_send())
    except Exception:
        logger.debug("[PERSEO_EVENTS] emit failed user=%s event=%s", user_id, event, exc_info=True)


def emit_generation_started(user_id: int, job_id: str, job_type: str) -> None:
    emit_perseo_event(user_id, "generation_started", {"job_id": job_id, "job_type": job_type})


def emit_generation_progress(user_id: int, job_id: str, progress: int, status: str = "processing") -> None:
    emit_perseo_event(
        user_id,
        "generation_progress",
        {"job_id": job_id, "progress": progress, "status": status},
    )


def emit_generation_completed(user_id: int, job_id: str, output: Dict[str, Any]) -> None:
    emit_perseo_event(
        user_id,
        "generation_completed",
        {"job_id": job_id, "output": output},
    )
