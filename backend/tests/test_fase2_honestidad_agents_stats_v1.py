"""Fase 2 / honestidad final #13 — GET /api/v1/agents/stats (valores fijos, sin uso) ya no existe."""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app


def test_agents_stats_eliminado():
    paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/api/v1/agents/stats" not in paths
    assert "/api/v1/agents/status" in paths
