"""Canonical execution_mode values for agent visibility (Phase A)."""

from __future__ import annotations

from typing import Literal, Optional

StandardExecutionMode = Literal["SIMULATED", "READ_ONLY", "REAL"]


def normalize_execution_mode(mode: Optional[str]) -> StandardExecutionMode:
    """Map control-layer modes to SIMULATED | READ_ONLY | REAL."""
    if not mode:
        return "SIMULATED"
    m = str(mode).upper()
    if m in ("REAL", "REAL_ACTIVE"):
        return "REAL"
    if m in ("READ_ONLY", "REAL_SAFE"):
        return "READ_ONLY"
    if m == "SIMULATED":
        return "SIMULATED"
    return "SIMULATED"
