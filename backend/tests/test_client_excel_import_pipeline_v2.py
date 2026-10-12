"""Tests for CLIENT_EXCEL_IMPORT_PIPELINE_V2."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.crm_import import CrmImportColumnMapping
from services.client_excel_import_pipeline_v2 import (
    PIPELINE_NAME,
    validate_clients,
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


def test_no_demo_boost_with_invented_amount():
    """Fase 2 / Step 2: se emitia un payment_due de 1500 EUR inventado (source=demo_boost)
    sobre el primer cliente si alguno superaba 1000 EUR."""
    import services.client_excel_import_pipeline_v2 as pipeline

    assert not hasattr(pipeline, "maybe_force_high_risk_demo")
    src = open(pipeline.__file__, encoding="utf-8").read()
    assert "demo_boost" not in src and "1500.0" not in src


def test_pipeline_name_constant():
    assert PIPELINE_NAME == "CLIENT_EXCEL_IMPORT_PIPELINE_V2"
