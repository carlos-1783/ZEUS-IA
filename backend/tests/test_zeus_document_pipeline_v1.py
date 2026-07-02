"""Tests for zeus_document_pipeline_v1."""

from unittest.mock import MagicMock

from services.zeus_document_pipeline_v1 import (
    analyze_document_perseo,
    process_financials_rafael,
    run_document_pipeline,
)


def test_analyze_document_low_risk_with_rgpd():
    doc = {
        "legal_document": {
            "content_preview": "# Contrato\nPartes: A · B\nRGPD 2016/679 cláusula larga " + "x" * 200
        }
    }
    out = analyze_document_perseo(doc)
    assert out["compliance"] is True
    assert out["risk_score"] < 0.7


def test_rafael_invoice_required_when_salary():
    doc = {"type": "contract"}
    payload = {"salary": 30000, "contract_type": "indefinido", "legal_document": {}}
    out = process_financials_rafael(doc, payload)
    assert out["invoice_required"] is True
    assert out["estimated_value"] == 30000


def test_run_document_pipeline_structure():
    db = MagicMock()
    user = MagicMock()
    user.id = 1
    payload = {
        "employee_name": "Test User",
        "salary": 25000,
        "legal_document": {
            "document_id": "test-uuid",
            "content_preview": "# Contrato\nPartes: Test · Empresa\nRGPD " + "y" * 300,
        },
    }
    result = run_document_pipeline(db, user, event_type="contract_rrhh_created", payload=payload)
    assert result["real_execution"] is True
    assert result["analysis"]["agent_source"] == "PERSEO"
    assert result["financial"]["agent_source"] == "RAFAEL"
    assert result["thalos"]["agent_source"] == "THALOS"
