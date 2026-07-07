"""Tests for CLIENT_EXCEL_IMPORT_PIPELINE_V2."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.crm_import import CrmImportColumnMapping
from services.client_excel_import_pipeline_v2 import (
    PIPELINE_NAME,
    validate_clients,
    maybe_force_high_risk_demo,
)


def test_validate_clients_requires_phone():
    mapping = CrmImportColumnMapping(name="nombre", phone=None)
    with pytest.raises(HTTPException) as exc:
        validate_clients([{"nombre": "Ana", "telefono": "+34600111222"}], mapping)
    assert exc.value.status_code == 400


def test_validate_clients_skips_invalid_phone():
    mapping = CrmImportColumnMapping(name="nombre", phone="telefono", importe="importe")
    rows = [
        {"nombre": "Ana", "telefono": "123", "importe": "100"},
        {"nombre": "Luis", "telefono": "+34600111222", "importe": "250.5"},
    ]
    clients, errors = validate_clients(rows, mapping)
    assert len(clients) == 1
    assert clients[0]["nombre"] == "Luis"
    assert clients[0]["importe"] == 250.5
    assert errors


def test_maybe_force_high_risk_demo_emits_when_importe_high():
    db = MagicMock()
    user = MagicMock()
    user.id = 1
    customer = MagicMock()
    customer.id = 42
    customer.name = "Big Client"
    customer.metadata_ = {"importe": 1200}

    with patch(
        "services.client_excel_import_pipeline_v2._emit_payment_due",
        return_value={"success": True},
    ) as mock_emit:
        emitted = maybe_force_high_risk_demo(db, user, [customer], trace_id="trace-1")

    assert emitted is True
    mock_emit.assert_called_once()
    assert mock_emit.call_args.kwargs["importe"] == 1500.0
    assert mock_emit.call_args.kwargs["source"] == "demo_boost"


def test_pipeline_name_constant():
    assert PIPELINE_NAME == "CLIENT_EXCEL_IMPORT_PIPELINE_V2"
