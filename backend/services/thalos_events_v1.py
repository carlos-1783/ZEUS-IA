"""THALOS WebSocket events."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_main_loop: Optional[asyncio.AbstractEventLoop] = None


def register_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def emit_thalos_event(user_id: int, event: str, data: Dict[str, Any]) -> None:
    payload = {"type": event, "source": "THALOS", **data}
    try:
        from app.api.v1.endpoints.websocket import manager

        async def _broadcast() -> None:
            if user_id:
                await manager.send_user_json(user_id, payload)
            else:
                msg = __import__("json").dumps(payload, default=str)
                await manager.broadcast(msg)

        loop = _main_loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(_broadcast(), loop)
        else:
            try:
                asyncio.get_running_loop().create_task(_broadcast())
            except RuntimeError:
                asyncio.run(_broadcast())
    except Exception:
        logger.debug("[THALOS_EVENTS] emit failed", exc_info=True)
