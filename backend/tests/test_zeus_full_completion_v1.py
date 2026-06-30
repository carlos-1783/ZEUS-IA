"""Tests zeus_full_completion_v1."""

from __future__ import annotations

from services.zeus_full_completion_v1 import PATCH_ID, _phase_endpoints, _phase_teamflow


def test_patch_id():
    assert PATCH_ID == "zeus_full_completion_v1"


def test_phase_1_and_2_pass():
    p1 = _phase_endpoints()
    p2 = _phase_teamflow()
    assert p1["passed"] is True
    assert p2["passed"] is True
