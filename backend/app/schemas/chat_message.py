"""Esquemas API mensajes de chat."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ChatMessageOut(BaseModel):
    id: int
    company_id: Optional[int] = None
    user_id: int
    agent_name: str
    thread_id: str
    role: str
    message: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ChatMessageListResponse(BaseModel):
    success: bool = True
    messages: List[ChatMessageOut] = Field(default_factory=list)
    total: int = 0
    agent_name: str = ""
    thread_id: str = "main"
