"""
Vuelta 6 de AUDIT_FIX_THALOS_SHIELD.md / AUDIT_THALOS_ESTRUCTURAL.md, sección 3
("hallazgo de mayor gravedad", derivado de la sección 14.2 de la ronda 5 de
revisión independiente).

Dos hallazgos bloqueantes cerrados aquí:

1. `services/automation/handlers/thalos_v1.py::handle_thalos_v1_cashflow`,
   `handle_thalos_v1_backup` y `handle_thalos_v1_alert` eran los 3 únicos
   handlers del `HANDLER_MAP` de THALOS sin el gate de superusuario que sí se
   aplicó a sus 3 hermanos (`handle_thalos_v1_detect`/`_monitor`/`_block`) en
   la Vuelta 5. Permitían a un usuario NO superusuario, vía
   `POST /api/v1/activities/log` + `AgentAutomationExecutor`, forjar un
   `company_id` ajeno, disparar `trigger_backup` (copia completa de la BD) y
   escribir una fila falsificada en `ThalosSecurityEvent` con el `company_id`
   de otra empresa.
2. `GET /api/v1/justice/compliance-events`
   (`app/api/v1/endpoints/justice.py`) descartaba `current_user` sin usarlo
   (mismo patrón `_ = current_user` que motivó 5 devoluciones en `thalos.py`/
   `thalos_v1.py`) y exponía `ComplianceEvent` (alimentado por `ThalosAlert`
   global sin `company_id`) a cualquier usuario autenticado.
"""

from __future__ import annotations

import uuid

import pytest  # pyright: ignore[reportMissingImports]
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.justice import justice_compliance_events
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from services.automation.handlers.thalos_v1 import (
    handle_thalos_v1_alert,
    handle_thalos_v1_backup,
    handle_thalos_v1_cashflow,
)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_company(db: Session, is_superuser: bool = False):
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"v6_estr_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Vuelta6 Estructural Tester",
        is_active=True,
        is_superuser=is_superuser,
    )
    company = Company(company_name=f"Vuelta6 Co {suf}", slug=f"v6-estr-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    return user, company


def _make_pending_activity(db: Session, *, agent_name: str, action_type: str, user_email, details=None) -> AgentActivity:
    row = AgentActivity(
        agent_name=agent_name,
        action_type=action_type,
        action_description="vuelta6 async engine test",
        details=details or {},
        user_email=user_email,
        status="pending",
        priority="normal",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 1) handle_thalos_v1_cashflow
# ---------------------------------------------------------------------------


def test_handle_thalos_v1_cashflow_blocks_normal_user_forging_foreign_company_id(db: Session):
    """Reproduce exactamente el escenario de 14.2: un atacante NO superusuario
    de una empresa forja el company_id de OTRA empresa en el body de la
    actividad para disparar una auditoría de cashflow ajena."""
    attacker, _ = _seed_company(db, is_superuser=False)
    _, victim_company = _seed_company(db, is_superuser=False)
    activity = _make_pending_activity(
        db,
        agent_name="THALOS",
        action_type="audit_cashflow_anomaly",
        user_email=attacker.email,
        details={"company_id": victim_company.id},
    )
    result = handle_thalos_v1_cashflow(activity)
    assert result["status"] == "blocked"
    assert result["details_update"]["thalos_v1"]["reason"] == "superuser_required_for_global_audit"


def test_handle_thalos_v1_cashflow_passes_gate_for_real_superuser(db: Session):
    admin, company = _seed_company(db, is_superuser=True)
    activity = _make_pending_activity(
        db,
        agent_name="THALOS",
        action_type="audit_cashflow_anomaly",
        user_email=admin.email,
        details={"company_id": company.id},
    )
    result = handle_thalos_v1_cashflow(activity)
    # Con THALOS_EXECUTION_ENABLED=False por defecto, el motor real responde
    # "skipped" -- confirma que pasó el gate de esta vuelta, no que quedó
    # bloqueado por él.
    assert result["details_update"]["thalos_v1"]["reason"] == "THALOS_EXECUTION_ENABLED is false"


# ---------------------------------------------------------------------------
# 2) handle_thalos_v1_backup
# ---------------------------------------------------------------------------


def test_handle_thalos_v1_backup_blocks_normal_user(db: Session):
    """Un usuario NO superusuario no debe poder disparar un backup completo
    de la base de datos de TODAS las empresas vía esta vía asíncrona."""
    attacker, _ = _seed_company(db, is_superuser=False)
    activity = _make_pending_activity(
        db, agent_name="THALOS", action_type="trigger_backup", user_email=attacker.email
    )
    result = handle_thalos_v1_backup(activity)
    assert result["status"] == "blocked"
    assert result["details_update"]["thalos_v1"]["reason"] == "superuser_required_for_global_audit"


def test_handle_thalos_v1_backup_passes_gate_for_real_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    activity = _make_pending_activity(
        db, agent_name="THALOS", action_type="trigger_backup", user_email=admin.email
    )
    result = handle_thalos_v1_backup(activity)
    assert result["details_update"]["thalos_v1"]["reason"] == "THALOS_EXECUTION_ENABLED is false"


# ---------------------------------------------------------------------------
# 3) handle_thalos_v1_alert -- el más grave: escribe una fila FORJADA en
#    ThalosSecurityEvent con el company_id elegido libremente por el atacante
# ---------------------------------------------------------------------------


def test_handle_thalos_v1_alert_blocks_normal_user_and_never_forges_security_event(db: Session):
    attacker, _ = _seed_company(db, is_superuser=False)
    _, victim_company = _seed_company(db, is_superuser=False)
    before_count = (
        db.query(ThalosSecurityEvent)
        .filter(ThalosSecurityEvent.company_id == victim_company.id)
        .count()
    )
    activity = _make_pending_activity(
        db,
        agent_name="THALOS",
        action_type="alert_admin",
        user_email=attacker.email,
        details={"company_id": victim_company.id, "message": "forged by attacker"},
    )
    result = handle_thalos_v1_alert(activity)
    assert result["status"] == "blocked"
    assert result["details_update"]["thalos_v1"]["reason"] == "superuser_required_for_global_audit"
    after_count = (
        db.query(ThalosSecurityEvent)
        .filter(ThalosSecurityEvent.company_id == victim_company.id)
        .count()
    )
    # Regresión directa del hallazgo de 14.2: no debe haberse escrito ninguna
    # fila nueva en ThalosSecurityEvent con el company_id ajeno forjado.
    assert after_count == before_count


def test_handle_thalos_v1_alert_passes_gate_for_real_superuser(db: Session):
    admin, company = _seed_company(db, is_superuser=True)
    activity = _make_pending_activity(
        db,
        agent_name="THALOS",
        action_type="alert_admin",
        user_email=admin.email,
        details={"company_id": company.id, "message": "legit alert"},
    )
    result = handle_thalos_v1_alert(activity)
    assert result["details_update"]["thalos_v1"]["reason"] == "THALOS_EXECUTION_ENABLED is false"


# ---------------------------------------------------------------------------
# 4) GET /api/v1/justice/compliance-events -- descartaba current_user sin
#    filtrar, exponiendo ComplianceEvent (alimentado por ThalosAlert global)
#    a cualquier usuario autenticado.
# ---------------------------------------------------------------------------


def test_justice_compliance_events_rejects_normal_user(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    with pytest.raises(HTTPException) as exc:
        justice_compliance_events(limit=50, current_user=user, db=db)
    assert exc.value.status_code == 403


def test_justice_compliance_events_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    result = justice_compliance_events(limit=50, current_user=admin, db=db)
    assert "events" in result or "data" in result


# ---------------------------------------------------------------------------
# 5) services/justice_cross_agent_v1.py::sync_cross_agent_events -- paso 4:
#    tras la migración de company_id, filtra las alertas THALOS por la
#    empresa real del usuario que dispara el audit, en vez de leer TODAS las
#    alertas abiertas de TODAS las empresas.
# ---------------------------------------------------------------------------


def test_sync_cross_agent_events_only_syncs_own_company_alerts(db: Session):
    from app.models.thalos_alert import ThalosAlert
    from services.justice_cross_agent_v1 import sync_cross_agent_events

    user_a, company_a = _seed_company(db, is_superuser=False)
    _, company_b = _seed_company(db, is_superuser=False)

    db.add(
        ThalosAlert(
            level="critical",
            title="Alerta de la empresa B",
            rule_id="v6_sweep_test_b",
            resolved=False,
            company_id=company_b.id,
        )
    )
    db.add(
        ThalosAlert(
            level="high",
            title="Alerta de la empresa A",
            rule_id="v6_sweep_test_a",
            resolved=False,
            company_id=company_a.id,
        )
    )
    db.commit()

    result = sync_cross_agent_events(db, user_a)
    db.commit()

    assert result["synced"]["thalos"] >= 1
    # No debe haberse escrito ningún compliance_event con el rule_id/título
    # de la alerta de la OTRA empresa.
    from app.models.compliance_event import ComplianceEvent

    rows = db.query(ComplianceEvent).filter(ComplianceEvent.source == "THALOS").all()
    assert not any("v6_sweep_test_b" in (r.details_json or "") for r in rows)


def test_sync_cross_agent_events_superuser_sees_all_companies(db: Session):
    from app.models.thalos_alert import ThalosAlert
    from services.justice_cross_agent_v1 import sync_cross_agent_events

    admin, _ = _seed_company(db, is_superuser=True)
    _, other_company = _seed_company(db, is_superuser=False)

    db.add(
        ThalosAlert(
            level="critical",
            title="Alerta ajena visible para superusuario",
            rule_id="v6_sweep_test_super",
            resolved=False,
            company_id=other_company.id,
        )
    )
    db.commit()

    result = sync_cross_agent_events(db, admin)
    db.commit()

    assert result["synced"]["thalos"] >= 1
