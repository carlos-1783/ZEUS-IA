"""Schemas for JUSTICIA system audit responses (justice_deep_audit_v1)."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

EvidenceSource = Literal["DB", "API", "NONE"]
DomainVerdict = Literal["REAL", "PARTIAL", "FAKE", "NONE", "ISOLATED", "CONTAMINATED"]
ExecutionMode = Literal["REAL", "SIMULATED", "READ_ONLY"]
SystemStatus = Literal["OPERATIONAL", "UNTRUSTED", "BROKEN", "INVALID"]


class AuditTraceItem(BaseModel):
    kind: Literal["endpoint", "table", "query", "flag"]
    ref: str
    detail: Optional[str] = None


class AuditConclusion(BaseModel):
    domain: str
    check: str
    status: Literal["PASS", "FAIL", "WARN", "GAP"]
    evidence_source: EvidenceSource
    detail: Optional[str] = None
    value: Optional[Any] = None


class DomainVerdictBlock(BaseModel):
    domain: str
    verdict: DomainVerdict
    checks_passed: int = 0
    checks_failed: int = 0
    notes: List[str] = Field(default_factory=list)


class JusticeAuditResponse(BaseModel):
    audit_id: str = "justice_deep_audit_v1"
    mode: str = "read_only_strict"
    execution_mode: ExecutionMode
    real_execution: bool
    audit_trace: List[AuditTraceItem]
    conclusions: List[AuditConclusion]
    domain_verdicts: Dict[str, DomainVerdictBlock]
    system_status: SystemStatus
    summary: str

    class Config:
        extra = "allow"
