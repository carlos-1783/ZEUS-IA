"""Tests rrhh_contract_service_v1."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from services.rrhh_contract_service_v1 import _find_employee, create_rrhh_contract_draft


def test_find_employee_missing_raises():
    db = MagicMock()
    user = MagicMock()
    with patch("services.rrhh_contract_service_v1.primary_company_id_for_user", return_value=1):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            _find_employee(db, user, employee_name="Nobody", employee_code="X")
    assert exc.value.status_code == 422


def test_create_contract_draft_calls_generator():
    db = MagicMock()
    user = MagicMock(id=1)
    emp = MagicMock(id=9, full_name="Ana", employee_code="E1", company_id=1, role_title="Dev")
    legal = {"document_id": "doc-uuid", "db_id": 3}

    with patch("services.rrhh_contract_service_v1.assert_can_write"), patch(
        "services.rrhh_contract_service_v1._find_employee", return_value=emp
    ), patch("services.rrhh_contract_service_v1.generate_contract", return_value=legal) as gen, patch(
        "services.rrhh_contract_service_v1.emit_event"
    ) as emit:
        out = create_rrhh_contract_draft(db, user, employee_name="Ana", employee_code="E1")

    assert out["success"] is True
    assert out["contract_id"] == "doc-uuid"
    gen.assert_called_once()
    emit.assert_called_once()
