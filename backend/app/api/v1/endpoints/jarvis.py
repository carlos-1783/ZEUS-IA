"""JARVIS = modo conversacional de ZEUS CORE (no es un agente nuevo).

`POST /api/v1/jarvis/message` es el PUNTO DE ENTRADA UNICO de la conversacion con ZEUS: alias
delgado de `POST /api/v1/chat/ZEUS CORE/chat`. No duplica logica: delega en el mismo
`chat_with_agent` (cadena JARVIS con request_id, guard THALOS por peticion, contexto de servidor
empresa/usuario, orquestador, memoria, auditoria). `/chat/{agent}/chat` sigue funcionando igual.

`GET /api/v1/jarvis/thread/{thread_id}` devuelve el historial del PROPIO usuario autenticado en ese
hilo (reutiliza chat_persistence_service.list_messages).

Canal: "text" o "voice" (modo Texto/Voz existente); el servidor solo lo registra como dato de la
cadena, la voz (STT/TTS) sigue en el cliente.
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.endpoints.chat import ChatRequest, ChatResponse, chat_with_agent
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat_message import ChatMessageListResponse, ChatMessageOut
from services import chat_persistence_service as chat_db
from services.thalos_request_guard_v1 import thalos_request_guard

router = APIRouter()

JARVIS_AGENT = "ZEUS CORE"


class JarvisMessageRequest(BaseModel):
    message: str
    thread_id: Optional[str] = Field(default=None, description="Hilo de conversacion; 'main' por defecto.")
    channel: Literal["text", "voice"] = "text"
    context: Optional[dict] = None


@router.post("/message", response_model=ChatResponse)
async def jarvis_message(
    request: JarvisMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(thalos_request_guard),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Mensaje a ZEUS CORE (JARVIS). Misma respuesta que /chat/ZEUS CORE/chat, incluido `request_id`."""
    ctx = dict(request.context or {})
    ctx["channel"] = request.channel  # el canal del cuerpo manda sobre el del contexto
    chat_request = ChatRequest(message=request.message, context=ctx, thread_id=request.thread_id)
    return await chat_with_agent(JARVIS_AGENT, chat_request, background_tasks, current_user, db)


@router.get("/thread/{thread_id}", response_model=ChatMessageListResponse)
async def jarvis_thread(
    thread_id: str,
    limit: int = Query(200, ge=1, le=500),
    current_user: User = Depends(thalos_request_guard),
    db: Session = Depends(get_db),
) -> ChatMessageListResponse:
    """Historial del propio usuario con ZEUS CORE en ese hilo y en SU empresa (resuelta en servidor).

    Pasa por el guard THALOS como el resto de rutas JARVIS (usuario activo y con empresa; el guard
    registra el evento). El historial de otra empresa del mismo usuario no se mezcla."""
    tid = (thread_id or "main").strip() or "main"
    company_id = chat_db.resolve_company_id(db, current_user)
    rows = chat_db.list_messages(
        db, user=current_user, agent_name=JARVIS_AGENT, thread_id=tid, limit=limit, company_id=company_id,
    )
    return ChatMessageListResponse(
        success=True,
        messages=[ChatMessageOut.model_validate(r) for r in rows],
        total=len(rows),
        agent_name=chat_db.normalize_agent_name(JARVIS_AGENT),
        thread_id=tid,
    )
