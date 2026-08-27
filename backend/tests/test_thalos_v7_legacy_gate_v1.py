"""
Vuelta 7 de AUDIT_THALOS_ESTRUCTURAL.md, sección 15.5/16.

El revisor de la ronda 6 (sección 15.5) encontró que
`services/automation/handlers/thalos.py` (archivo legacy, distinto de
`thalos_v1.py`, nunca auditado en las 6 rondas anteriores) registra 3
acciones en `HANDLER_MAP["THALOS"]` (`security_scan`, `task_assigned` ->
alerts, `backup_created`) sin ningún gate de superusuario, pese a ser
alcanzables por el mismo vector asíncrono
(`POST /api/v1/activities/log` -> `AgentAutomationExecutor` ->
`resolve_handler`) que ya se cerró para sus hermanas de `thalos_v1.py` en la
Vuelta 6. La más grave, `handle_thalos_backup`, permitía a cualquier usuario
autenticado NO superusuario disparar una copia completa real de `zeus.db`
(base de datos de TODAS las empresas) — reproducido en vivo por el revisor.

Esta vuelta reutiliza exactamente `thalos_v1._is_superuser_email` (mismo
patrón ya validado, sin duplicar lógica) para gatear las 3 funciones.
"""

from __future__ import annotations

import glob
import os
import uuid

import pytest  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.user import User
from services.automation.handlers.thalos import (
    handle_thalos_alerts,
    handle_thalos_backup,
    handle_thalos_security_scan,
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
        email=f"v7_legacy_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Vuelta7 Legacy Tester",
        is_active=True,
        is_superuser=is_superuser,
    )
    company = Company(company_name=f"Vuelta7 Co {suf}", slug=f"v7-legacy-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    return user, company


def _make_pending_activity(db: Session, *, agent_name: str, action_type: str, user_email) -> AgentActivity:
    row = AgentActivity(
        agent_name=agent_name,
        action_type=action_type,
        action_description="vuelta7 legacy handler gate test",
        details={},
        user_email=user_email,
        status="pending",
        priority="normal",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 1) handle_thalos_backup (action_type=backup_created) -- el hallazgo mas
#    grave: permitia una copia completa real de zeus.db a cualquier usuario
#    autenticado no superusuario.
# ---------------------------------------------------------------------------


def test_handle_thalos_backup_blocks_normal_user_and_creates_no_file(db: Session):
    attacker, _ = _seed_company(db, is_superuser=False)
    backup_dir = os.path.join("storage", "backups")
    before = set(glob.glob(os.path.join(backup_dir, "*.db")))

    activity = _make_pending_activity(
        db, agent_name="THALOS", action_type="backup_created", user_email=attacker.email
    )
    result = handle_thalos_backup(activity)

    assert result["status"] == "blocked"
    assert result["details_update"]["automation"]["reason"] == "superuser_required_for_global_audit"

    after = set(glob.glob(os.path.join(backup_dir, "*.db")))
    assert after - before == set(), "el atacante NO debe poder crear un backup real"


def test_handle_thalos_backup_passes_gate_for_real_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    backup_dir = os.path.join("storage", "backups")
    before = set(glob.glob(os.path.join(backup_dir, "*.db")))

    activity = _make_pending_activity(
        db, agent_name="THALOS", action_type="backup_created", user_email=admin.email
    )
    result = handle_thalos_backup(activity)

    assert result["status"] != "blocked"

    # Limpieza: esta acción legacy sí ejecuta un shutil.copy2 real (no está
    # gateada por THALOS_EXECUTION_ENABLED como su hermana de thalos_v1.py),
    # así que el control positivo puede dejar un fichero real -- se elimina
    # aquí para no dejar backups huérfanos generados por la suite de tests.
    after = set(glob.glob(os.path.join(backup_dir, "*.db")))
    for f in after - before:
        os.remove(f)


# ---------------------------------------------------------------------------
# 2) handle_thalos_security_scan (action_type=security_scan) y
#    handle_thalos_alerts (action_type=task_assigned) -- severidad menor
#    (no leen/escriben datos de otra empresa) pero misma clase de hallazgo,
#    documentada en la sección 15.5 y cerrada en la misma vuelta.
# ---------------------------------------------------------------------------


def test_handle_thalos_security_scan_blocks_normal_user(db: Session):
    attacker, _ = _seed_company(db, is_superuser=False)
    activity = _make_pending_activity(
        db, agent_name="THALOS", action_type="security_scan", user_email=attacker.email
    )
    result = handle_thalos_security_scan(activity)
    assert result["status"] == "blocked"
    assert result["details_update"]["automation"]["reason"] == "superuser_required_for_global_audit"


def test_handle_thalos_security_scan_passes_gate_for_real_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    activity = _make_pending_activity(
        db, agent_name="THALOS", action_type="security_scan", user_email=admin.email
    )
    result = handle_thalos_security_scan(activity)
    assert result["status"] != "blocked"


def test_handle_thalos_alerts_blocks_normal_user(db: Session):
    attacker, _ = _seed_company(db, is_superuser=False)
    activity = _make_pending_activity(
        db, agent_name="THALOS", action_type="task_assigned", user_email=attacker.email
    )
    result = handle_thalos_alerts(activity)
    assert result["status"] == "blocked"
    assert result["details_update"]["automation"]["reason"] == "superuser_required_for_global_audit"


def test_handle_thalos_alerts_passes_gate_for_real_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    activity = _make_pending_activity(
        db, agent_name="THALOS", action_type="task_assigned", user_email=admin.email
    )
    result = handle_thalos_alerts(activity)
    assert result["status"] != "blocked"
