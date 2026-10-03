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


def _schedule(coro_factory) -> None:
    """Agenda una corutina en el loop principal registrado, o la ejecuta
    inline si no hay loop corriendo (p.ej. en tests síncronos)."""
    loop = _main_loop
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(coro_factory(), loop)
    else:
        try:
            asyncio.get_running_loop().create_task(coro_factory())
        except RuntimeError:
            asyncio.run(coro_factory())


def emit_thalos_event(user_id: int, event: str, data: Dict[str, Any]) -> None:
    """Emite un evento THALOS a un usuario concreto.

    No existe (ni debe existir) un fallback de "broadcast a todas las
    conexiones": un evento sin `user_id` resuelto no debe llegar a usuarios
    de otras empresas conectados por WebSocket -- eso era exactamente la
    fuga multi-tenant reportada (THALOS difundía alertas de seguridad de una
    empresa a TODOS los tenants conectados vía `manager.broadcast`). Mismo
    patrón que `services/perseo_events_v1.py::emit_perseo_event`.

    Para eventos de seguridad asociados a una empresa (p.ej. alertas), usar
    `emit_thalos_event_for_company`, que resuelve los usuarios reales de esa
    empresa antes de notificarles.
    """
    if not user_id:
        logger.debug("[THALOS_EVENTS] sin user_id -- evento no difundido (ver emit_thalos_event_for_company): %s", event)
        return
    payload = {"type": event, "source": "THALOS", **data}
    try:
        from app.api.v1.endpoints.websocket import manager

        async def _send() -> None:
            await manager.send_user_json(user_id, payload)

        _schedule(_send)
    except Exception:
        logger.debug("[THALOS_EVENTS] emit failed", exc_info=True)


def emit_thalos_event_for_company(db: Any, company_id: Optional[int], event: str, data: Dict[str, Any]) -> None:
    """Emite un evento THALOS SOLO a los usuarios conectados que pertenecen
    a `company_id` (resuelto vía `UserCompany`).

    Si `company_id` es `None` (alerta sin empresa identificada -- p.ej.
    fuerza bruta con un email inexistente, ver
    `thalos_alert_service._resolve_company_id_for_email`), el evento NO se
    difunde en tiempo real: queda persistido en BD y accesible vía los
    endpoints REST ya protegidos (`_require_superuser_for_global_audit` en
    `app/api/v1/endpoints/thalos.py`). Nunca se hace broadcast ciego a todas
    las conexiones -- eso es precisamente la fuga multi-tenant que esta
    función corrige.
    """
    if not company_id:
        logger.debug("[THALOS_EVENTS] sin company_id resuelto -- no se difunde por WS: %s", event)
        return
    payload = {"type": event, "source": "THALOS", "company_id": company_id, **data}
    try:
        from app.api.v1.endpoints.websocket import manager
        from app.models.company import UserCompany

        user_ids = [
            row[0]
            for row in db.query(UserCompany.user_id)
            .filter(UserCompany.company_id == company_id)
            .distinct()
            .all()
        ]
        if not user_ids:
            logger.debug("[THALOS_EVENTS] company_id=%s sin usuarios -- nada que difundir: %s", company_id, event)
            return

        async def _send_to_company() -> None:
            for uid in user_ids:
                await manager.send_user_json(uid, payload)

        _schedule(_send_to_company)
    except Exception:
        logger.debug("[THALOS_EVENTS] emit_for_company failed", exc_info=True)
