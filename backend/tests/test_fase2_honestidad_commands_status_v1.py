"""Fase 2 / honestidad final #27 — GET /api/v1/commands/status ("operational" fijo) eliminado."""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app


def test_commands_status_eliminado():
    routes = {(r.path, m) for r in app.routes if isinstance(r, APIRoute) for m in r.methods}
    assert ("/api/v1/commands/status", "GET") not in routes
    assert ("/api/v1/commands/execute", "POST") in routes
