"""Fase 2 / Step 2 — el plan pre-lanzamiento (plantilla interna de ZEUS IA) ya no se
entrega a cualquier cliente como si fuera suyo."""

from unittest.mock import patch

from agents.zeus_core import ZeusCore


def test_client_asking_prelaunch_does_not_get_platform_plan():
    z = ZeusCore()
    with patch.object(z, "_start_prelaunch_phase") as start, \
         patch.object(z, "_route_to_agent", return_value=None), \
         patch.object(z, "_handle_directly", return_value={"content": "ok"}):
        z.process_request({"user_message": "quiero un plan de pre-lanzamiento", "_is_superuser": False})
    start.assert_not_called()


def test_superuser_and_internal_init_still_get_it():
    z = ZeusCore()
    with patch.object(z, "_start_prelaunch_phase", return_value={"success": True}) as start:
        z.process_request({"user_message": "pre-lanzamiento", "_is_superuser": True})
        z.process_request({"user_message": "", "phase": "prelaunch", "origin": "auto-init"})
    assert start.call_count == 2
