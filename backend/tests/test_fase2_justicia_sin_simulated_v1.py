"""Fase 2 / Step 2 — JUSTICIA ya no etiqueta como SIMULATED sus respuestas reales."""

from unittest.mock import patch

from agents.justicia import Justicia
from app.core.config import settings


def _run(ctx, audit_flag):
    j = Justicia()
    with patch.object(j, "make_decision", return_value={"content": "respuesta del LLM"}), \
         patch.object(settings, "JUSTICE_REAL_AUDIT_ENABLED", audit_flag):
        return j.process_request(ctx)


def test_llm_advice_is_read_only_not_simulated():
    r = _run({"type": "general", "message": "duda"}, True)
    assert r["execution_mode"] == "READ_ONLY"


def test_audit_disabled_says_not_executed():
    r = _run({"type": "audit", "message": "audita", "user_id": 1}, False)
    assert r["execution_mode"] == "NOT_EXECUTED"
    assert r["system_audit"]["executed"] is False and "NO ejecutada" in r["system_audit"]["summary"]
    assert "SIMULATED" not in str(r)


def test_audit_failure_is_error(monkeypatch):
    import services.justice_system_audit_v1 as sa

    def boom(*a, **k):
        raise RuntimeError("db caida")

    monkeypatch.setattr(sa, "run_system_audit", boom)

    class _Q:
        def filter(self, *a): return self
        def first(self): return object()

    class _DB:
        def query(self, *a): return _Q()
        def close(self): pass

    with patch("app.db.session.SessionLocal", _DB):
        r = _run({"type": "audit", "message": "audita", "user_id": 1}, True)
    assert r["execution_mode"] == "ERROR" and r["system_audit"]["executed"] is False
