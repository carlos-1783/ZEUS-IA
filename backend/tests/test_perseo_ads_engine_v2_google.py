"""Regresión: create_google_campaign() nunca debe devolver un éxito falso.

Hallazgo histórico (AUDITORIA_TOTAL_FINAL.md, sección 1, fila PERSEO): cuando
GOOGLE_ADS_CUSTOMER_ID / GOOGLE_ADS_DEVELOPER_TOKEN estaban presentes pero no
existía cliente real de la Google Ads API, la función devolvía
{"success": True, "campaign_id": None, "simulated": False, ...} — un éxito
falso que ocultaba que la campaña NUNCA se creó en Google Ads.

Ya corregido en el historial de esta rama (commit 2346230): ahora la función
falla explícitamente con HTTPException (503 si no está configurado, 501 si
está configurado pero no hay integración real). Este test evita que el bug
reaparezca.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from services.perseo_ads_engine_v2 import create_ad_campaign, create_google_campaign


def test_google_campaign_not_configured_fails_honestly(monkeypatch):
    monkeypatch.delenv("GOOGLE_ADS_CUSTOMER_ID", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        create_google_campaign(name="Test", daily_budget_micros=1_000_000)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"] == "google_ads_not_configured"


def test_google_campaign_configured_without_real_client_fails_honestly(monkeypatch):
    """Caso exacto del hallazgo: credenciales presentes pero sin cliente real.

    Nunca debe devolver success=True con campaign_id=None ni simulated=False
    sin haber ejecutado una llamada real a la API de Google Ads.
    """
    monkeypatch.setenv("GOOGLE_ADS_CUSTOMER_ID", "1234567890")
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "fake-test-token-not-real")

    with pytest.raises(HTTPException) as exc_info:
        create_google_campaign(name="Test Revisor", daily_budget_micros=10_000_000)

    assert exc_info.value.status_code == 501
    assert exc_info.value.detail["error"] == "google_ads_client_not_implemented"


def test_create_ad_campaign_google_end_to_end_fails_honestly_when_writes_enabled(monkeypatch):
    """Incluso con writes_enabled=True (modo REAL) la ruta google nunca finge éxito."""
    monkeypatch.setenv("GOOGLE_ADS_CUSTOMER_ID", "1234567890")
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "fake-test-token-not-real")

    with patch(
        "services.perseo_ads_engine_v2.get_execution_status",
        return_value={"execution_mode": "REAL", "writes_enabled": True},
    ):
        with pytest.raises(HTTPException) as exc_info:
            create_ad_campaign(
                db=None,
                user=None,
                platform="google",
                name="Test Revisor End-to-End",
                budget=100.0,
                transaction_id="tx-test-1",
            )

    assert exc_info.value.status_code == 501
    assert exc_info.value.detail["error"] == "google_ads_client_not_implemented"
