"""Fase 2 / Step 2 — herramientas de workspace que inventaban resultados.

- record_face_check_in "aprobaba" fichajes con una puntuacion sacada del hash del id (sin
  comparar ninguna cara); build_employee_schedule y create_rrhh_contract rellenaban datos.
  Sin usos: eliminadas.
- /workspaces/rafael/forms sin empresa generaba un 303 "ready" con IVA soportado inventado.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

import services.workspaces as tools


def test_fake_tools_removed():
    for name in ("record_face_check_in", "build_employee_schedule", "create_rrhh_contract", "generate_fiscal_forms"):
        assert not hasattr(tools, name)


def test_forms_without_company_is_403_not_invented():
    from app.api.v1.endpoints import workspaces as ws

    req = SimpleNamespace(model_dump=lambda: {"revenue": 1000, "expenses": 500})
    with patch("services.crm_office_service.primary_company_id", return_value=None), \
         patch.object(ws, "_persist_agent_tool_response") as persist:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(ws.workspace_rafael_forms(req, current_user=SimpleNamespace(id=1), db=None))
    assert exc.value.status_code == 403
    persist.assert_not_called()
