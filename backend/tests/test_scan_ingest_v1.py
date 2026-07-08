"""Tests for unified physical scan pipeline v2."""

from __future__ import annotations

import pytest

from services.scan_flow_service_v1 import _parse_qr_data
from services.scan_normalizer_v1 import normalize_nfc_payload, normalize_scan_type, normalize_text_payload


def test_normalize_scan_type_aliases():
    assert normalize_scan_type("QR_SCAN") == "qr"
    assert normalize_scan_type("NFC_SCAN") == "nfc"
    assert normalize_scan_type("MRZ_SCAN") == "mrz"
    assert normalize_scan_type("dni") == "mrz"


def test_normalize_scan_type_invalid():
    with pytest.raises(ValueError, match="no soportado"):
        normalize_scan_type("BLE_SCAN")


def test_normalize_text_payload():
    assert normalize_text_payload("  hola  ") == "hola"
    assert normalize_text_payload(None) == ""


def test_normalize_nfc_payload_prefers_text():
    text, hex_payload = normalize_nfc_payload("ZEUSCHECK|W1|t", "abcd")
    assert text == "ZEUSCHECK|W1|t"
    assert hex_payload == "abcd"


def test_parse_qr_client_action_format():
    parsed = _parse_qr_data("CLIENT|42|VIEW")
    assert parsed["kind"] == "client_action"
    assert parsed["customer_ref"] == "42"
    assert parsed["action"] == "VIEW"


def test_parse_qr_client_checkin_action():
    parsed = _parse_qr_data("CLIENT|W001|CHECKIN")
    assert parsed["kind"] == "client_action"
    assert parsed["action"] == "CHECKIN"
