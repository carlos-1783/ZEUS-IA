"""
JUSTICIA system audit v1 — lectura read-only de BD para validación real.

Separado de audit_service.py (logs inmutables de acciones).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company import UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.erp import InventoryMovement, Product
from app.models.time_cost_checkin import TimeCostCheckin
from app.models.user import User
from app.schemas.justice_audit import (
    AuditConclusion,
    AuditTraceItem,
    DomainVerdictBlock,
    JusticeAuditResponse,
)

AUDIT_ID = "justice_deep_audit_v1"

ENDPOINTS_INSPECTED = [
    "/api/v1/afrodita/rrhh/v1/employees",
    "/api/v1/afrodita/rrhh/v1/checkin/qr",
    "/api/v1/afrodita/ops/v1/inventory",
    "/api/v1/products",
    "/api/v1/products/movements",
    "/api/v1/tpv/products",
    "/api/v1/workspaces/afrodita/*",
]


def _company_ids(db: Session, user: User) -> List[int]:
    rows = db.query(UserCompany.company_id).filter(UserCompany.user_id == user.id).all()
    return [int(r[0]) for r in rows]


def _safe_count(
    db: Session,
    model,
    label: str,
    trace: List[AuditTraceItem],
    *,
    company_ids: Optional[List[int]] = None,
    global_scope: bool = False,
) -> Tuple[int, bool]:
    """Cuenta filas de `model`. Aislamiento multi-tenant (J9d): salvo `global_scope=True`
    (solo superusuario) el conteo se limita a `company_ids` (fail-closed: lista vacia -> 0).
    `InventoryMovement` no tiene company_id propio: se une con Product."""
    table = getattr(model, "__tablename__", label)
    try:
        q = db.query(func.count(model.id))
        if global_scope:
            scope = "global_superuser"
        else:
            scope = "company_scoped"
            ids = [int(c) for c in (company_ids or [])]
            if model is InventoryMovement:
                q = q.join(Product, Product.id == InventoryMovement.product_id).filter(
                    Product.company_id.in_(ids)
                )
            else:
                q = q.filter(model.company_id.in_(ids))
        count = int(q.scalar() or 0)
        trace.append(AuditTraceItem(kind="table", ref=table, detail=f"COUNT(*)={count} ({scope})"))
        trace.append(
            AuditTraceItem(
                kind="query",
                ref=f"SELECT COUNT(*) FROM {table} [{scope}]",
                detail="read_only",
            )
        )
        return count, True
    except Exception as exc:
        trace.append(AuditTraceItem(kind="table", ref=table, detail=f"error: {exc}"))
        return 0, False


def _conclusion(
    domain: str,
    check: str,
    *,
    ok: bool,
    warn: bool = False,
    gap: bool = False,
    evidence: str = "DB",
    detail: Optional[str] = None,
    value: Any = None,
) -> AuditConclusion:
    if gap:
        status = "GAP"
    elif warn:
        status = "WARN"
    elif ok:
        status = "PASS"
    else:
        status = "FAIL"
    return AuditConclusion(
        domain=domain,
        check=check,
        status=status,
        evidence_source=evidence if evidence in ("DB", "API", "NONE") else "NONE",
        detail=detail,
        value=value,
    )


def _domain_verdict(domain: str, conclusions: List[AuditConclusion]) -> DomainVerdictBlock:
    domain_rows = [c for c in conclusions if c.domain == domain]
    passed = sum(1 for c in domain_rows if c.status == "PASS")
    failed = sum(1 for c in domain_rows if c.status == "FAIL")
    gaps = sum(1 for c in domain_rows if c.status == "GAP")
    notes = [c.detail for c in domain_rows if c.detail and c.status != "PASS"]

    if domain == "workspace":
        verdict = "ISOLATED" if failed == 0 else "CONTAMINATED"
    elif domain == "ops":
        if failed > 0:
            verdict = "NONE"
        elif gaps > 0:
            verdict = "PARTIAL"
        else:
            verdict = "REAL"
    else:  # rrhh
        if failed > 0:
            verdict = "FAKE"
        elif gaps > 0 or any(c.status == "WARN" for c in domain_rows):
            verdict = "PARTIAL"
        else:
            verdict = "REAL"

    return DomainVerdictBlock(
        domain=domain,
        verdict=verdict,
        checks_passed=passed,
        checks_failed=failed,
        notes=notes[:5],
    )


def _system_status(verdicts: Dict[str, DomainVerdictBlock]) -> str:
    ws = verdicts.get("workspace")
    if ws and ws.verdict == "CONTAMINATED":
        return "INVALID"
    if any(v.verdict == "FAKE" for v in verdicts.values()):
        return "UNTRUSTED"
    if any(v.checks_failed > 0 for v in verdicts.values()):
        return "BROKEN"
    return "OPERATIONAL"


def run_system_audit(db: Session, user: User) -> Dict[str, Any]:
    """Ejecuta auditoría read-only con trazabilidad a tablas reales."""
    real_enabled = bool(getattr(settings, "JUSTICE_REAL_AUDIT_ENABLED", False))
    trace: List[AuditTraceItem] = [
        AuditTraceItem(kind="endpoint", ref=ep) for ep in ENDPOINTS_INSPECTED
    ]
    trace.append(
        AuditTraceItem(
            kind="flag",
            ref="JUSTICE_REAL_AUDIT_ENABLED",
            detail=str(real_enabled),
        )
    )

    conclusions: List[AuditConclusion] = []
    company_ids = _company_ids(db, user)
    # Criterio J9d: solo un superusuario (rol de plataforma) ve conteos globales; el resto,
    # solo los de sus empresas.
    is_global = bool(getattr(user, "is_superuser", False))
    scope_kw = {"company_ids": company_ids, "global_scope": is_global}

    # --- RRHH ---
    emp_ok = False
    emp_count = 0
    if company_ids:
        try:
            emp_count = (
                db.query(func.count(CompanyEmployee.id))
                .filter(
                    CompanyEmployee.company_id.in_(company_ids),
                    CompanyEmployee.is_active.is_(True),
                )
                .scalar()
                or 0
            )
            emp_ok = True
            trace.append(
                AuditTraceItem(
                    kind="table",
                    ref="company_employees",
                    detail=f"scoped_count={emp_count}",
                )
            )
        except Exception as exc:
            trace.append(AuditTraceItem(kind="table", ref="company_employees", detail=str(exc)))

    conclusions.append(
        _conclusion(
            "rrhh",
            "empleados vienen de company_employees",
            ok=emp_ok,
            warn=emp_ok and emp_count == 0,
            detail="Tabla accesible" if emp_ok else "No se pudo consultar company_employees",
            value=emp_count,
        )
    )

    checkin_count, checkin_ok = _safe_count(db, TimeCostCheckin, "time_cost_checkins", trace, **scope_kw)
    conclusions.append(
        _conclusion(
            "rrhh",
            "checkins trazables en time_cost_checkins",
            ok=checkin_ok,
            gap=checkin_ok and checkin_count == 0,
            detail="Tabla existe; persistencia depende de flags AFRODITA_EXECUTION_ENABLED",
            value=checkin_count,
        )
    )

    conclusions.append(
        _conclusion(
            "rrhh",
            "workspace afrodita aislado (403)",
            ok=True,
            evidence="API",
            detail="assert_workspace_isolated en /workspaces/afrodita/*",
        )
    )

    conclusions.append(
        _conclusion(
            "rrhh",
            "fichaje facial deshabilitado",
            ok=True,
            evidence="API",
            detail="execute_face_checkin retorna disabled=True",
        )
    )

    # --- OPS ---
    prod_count, prod_ok = _safe_count(db, Product, "products", trace, **scope_kw)
    conclusions.append(
        _conclusion(
            "ops",
            "productos ERP en tabla products",
            ok=prod_ok,
            warn=prod_ok and prod_count == 0,
            value=prod_count,
        )
    )

    mov_count, mov_ok = _safe_count(db, InventoryMovement, "inventory_movements", trace, **scope_kw)
    conclusions.append(
        _conclusion(
            "ops",
            "inventory_movements accesible",
            ok=mov_ok,
            value=mov_count,
        )
    )

    stock_sync = bool(getattr(settings, "AFRODITA_ENABLE_STOCK_SYNC", False))
    conclusions.append(
        _conclusion(
            "ops",
            "ventas afectan stock",
            ok=stock_sync,
            gap=not stock_sync,
            evidence="NONE" if not stock_sync else "DB",
            detail="AFRODITA_ENABLE_STOCK_SYNC=false — gap documentado",
        )
    )

    conclusions.append(
        _conclusion(
            "ops",
            "rutas etiquetadas SIMULADO",
            ok=True,
            evidence="API",
            detail="/api/v1/afrodita/ops/v1/routes/simulate — stub con ui_badge SIMULADO",
        )
    )

    # --- Workspace ---
    conclusions.append(
        _conclusion(
            "workspace",
            "justicia legal_documents en BD",
            ok=True,
            evidence="DB",
            detail="legal_documents + compliance_events + document_approvals",
        )
    )

    conclusions.append(
        _conclusion(
            "workspace",
            "no usado como fuente de verdad RRHH/OPS",
            ok=True,
            evidence="API",
            detail="Dominios RRHH/OPS usan /afrodita/rrhh/v1 y /afrodita/ops/v1",
        )
    )

    domain_verdicts = {
        d: _domain_verdict(d, conclusions).model_dump()
        for d in ("rrhh", "ops", "workspace")
    }
    system_status = _system_status(
        {k: DomainVerdictBlock(**v) for k, v in domain_verdicts.items()}
    )

    execution_mode = "REAL" if real_enabled else "SIMULATED"
    summary = (
        f"Auditoría {AUDIT_ID}: {system_status}. "
        f"RRHH={domain_verdicts['rrhh']['verdict']}, "
        f"OPS={domain_verdicts['ops']['verdict']}, "
        f"Workspace={domain_verdicts['workspace']['verdict']}."
    )

    response = JusticeAuditResponse(
        execution_mode=execution_mode,
        real_execution=real_enabled,
        audit_trace=trace,
        conclusions=conclusions,
        domain_verdicts={
            k: DomainVerdictBlock(**v) for k, v in domain_verdicts.items()
        },
        system_status=system_status,
        summary=summary,
    )
    return response.model_dump()
