"""Middleware opt-in: registra intentos de login para THALOS (sin modificar auth.py)."""

from __future__ import annotations

import json
import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.db.session import SessionLocal
from services.thalos_security_engine import record_login_attempt

logger = logging.getLogger(__name__)

_LOGIN_PATHS = frozenset({"/api/v1/auth/login", "/api/v1/auth/token"})


class ThalosLoginAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.THALOS_REAL_MONITORING:
            return await call_next(request)

        path = request.url.path.rstrip("/") or request.url.path
        is_login = any(path.endswith(p.rstrip("/")) for p in _LOGIN_PATHS)
        body_bytes = b""
        email = ""

        if is_login and request.method.upper() == "POST":
            body_bytes = await request.body()

            async def receive():
                return {"type": "http.request", "body": body_bytes, "more_body": False}

            request = Request(request.scope, receive)
            try:
                data = json.loads(body_bytes.decode("utf-8") or "{}")
                email = str(data.get("email") or data.get("username") or "").strip().lower()
            except (json.JSONDecodeError, UnicodeDecodeError):
                email = ""

        response = await call_next(request)

        if is_login and email:
            ip = request.client.host if request.client else None
            success = 200 <= response.status_code < 300
            db = SessionLocal()
            try:
                record_login_attempt(db, email=email, ip_address=ip, success=success)
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("thalos login audit failed")
            finally:
                db.close()

        return response
