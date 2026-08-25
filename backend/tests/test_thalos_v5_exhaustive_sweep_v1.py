"""
Vuelta 5 de AUDIT_FIX_THALOS_SHIELD.md (sección 12.2/12.3): la ronda 4 de
revisión independiente confirmó en vivo, con una cuenta 100% nueva y sin
ninguna precondición, que al menos 3 rutas hermanas del mismo motor de
auditoría global (`thalos_security_engine.scan_logs` /
`thalos_threat_engine.evaluate_events` / `thalos_monitor_service.audit_from_db`
/ `thalos_alert_service.list_alerts`/`resolve_alert`) seguían sin ningún gate:

- POST /api/v1/workspaces/thalos/threat-detector (workspace_thalos_threat)
- GET  /api/v1/thalos/v1/events (thalos_v1_events)
- GET  /api/v1/thalos/v1/alerts (thalos_v1_alerts)

Y, al agotar el mapa completo del router legacy no versionado
`/api/v1/thalos/*` (nunca revisado en las 4 vueltas previas), se encontraron
otros 6 endpoints con el mismo patrón (`thalos.py`): status, events, alerts,
resolve_alert, audit, monitor, logs/ingest.

Este archivo cubre, en un solo lugar, los tests de regresión de TODOS los
gates de la Vuelta 5, más 2 hallazgos nuevos encontrados durante el barrido
exhaustivo pedido para esta ronda (ver AUDIT_FIX_THALOS_SHIELD.md, sección
13):

1. GET /api/v1/thalos/v1/status (thalos_v1_status) — sin gate, incrustaba
   `audit_from_db()` bajo la clave `database` sin restricción.
2. POST /api/v1/activities/log (activities.py::log_activity) — SIN NINGUNA
   autenticación y con `user_email` controlado por el cliente; alimentaba
   `AgentAutomationExecutor` (proceso en segundo plano) que ejecuta los
   handlers reales de THALOS v1
   (`services/automation/handlers/thalos_v1.py`), permitiendo en teoría
   disparar el motor global (o incluso `block_user` cross-tenant) sin ninguna
   cuenta. Se corrige exigiendo autenticación real y forzando
   `user_email = current_user.email` server-side (ignorando el valor del
   cliente), más un gate de superusuario re-verificado dentro de los propios
   handlers asíncronos (que no tienen acceso a un `current_user` de FastAPI).
"""

from __future__ import annotations

import asyncio
import uuid

import pytest  # pyright: ignore[reportMissingImports]
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints.thalos import (
    LogIngestBody,
    thalos_alerts,
    thalos_audit,
    thalos_events,
    thalos_ingest_logs,
    thalos_monitor_now,
    thalos_resolve_alert,
    thalos_status,
)
from app.api.v1.endpoints.thalos_v1 import thalos_v1_alerts, thalos_v1_events, thalos_v1_status
from app.api.v1.endpoints.workspaces import ThalosThreatRequest, workspace_thalos_threat
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.thalos_alert import ThalosAlert
from app.models.thalos_event import ThalosEvent
from app.models.user import User
from services.automation.handlers.thalos_v1 import (
    handle_thalos_v1_block,
    handle_thalos_v1_detect,
    handle_thalos_v1_monitor,
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
        email=f"v5_sweep_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Vuelta5 Sweep Tester",
        is_active=True,
        is_superuser=is_superuser,
    )
    company = Company(company_name=f"Vuelta5 Co {suf}", slug=f"v5-sweep-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    return user, company


def _seed_event_and_alert(db: Session) -> None:
    """Al menos un ThalosEvent/ThalosAlert real para que las rutas de
    superusuario no fallen con 404 por 'sin datos', y para poder ejercer
    thalos_resolve_alert de verdad."""
    row = ThalosEvent(
        event_type="test_event",
        severity="high",
        message="evento de prueba vuelta 5",
        source="test_suite",
    )
    db.add(row)
    db.flush()
    alert = ThalosAlert(
        event_id=row.id,
        level="high",
        title="Alerta de prueba vuelta 5",
        message="mensaje de prueba",
        rule_id=f"v5_test_{uuid.uuid4().hex[:6]}",
        resolved=False,
    )
    db.add(alert)
    db.commit()
    return alert.id


# ---------------------------------------------------------------------------
# 1) Router legacy /api/v1/thalos/* (thalos.py) — 7 endpoints
# ---------------------------------------------------------------------------


def test_thalos_legacy_status_rejects_normal_user(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    with pytest.raises(HTTPException) as excinfo:
        thalos_status(current_user=user, db=db)
    assert excinfo.value.status_code == 403


def test_thalos_legacy_status_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    result = thalos_status(current_user=admin, db=db)
    assert result is not None


def test_thalos_legacy_events_rejects_normal_user(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    with pytest.raises(HTTPException) as excinfo:
        thalos_events(current_user=user, db=db)
    assert excinfo.value.status_code == 403


def test_thalos_legacy_events_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    _seed_event_and_alert(db)
    result = thalos_events(current_user=admin, db=db)
    assert result is not None


def test_thalos_legacy_alerts_rejects_normal_user(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    with pytest.raises(HTTPException) as excinfo:
        thalos_alerts(current_user=user, db=db)
    assert excinfo.value.status_code == 403


def test_thalos_legacy_alerts_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    _seed_event_and_alert(db)
    result = thalos_alerts(current_user=admin, db=db)
    assert result is not None


def test_thalos_legacy_resolve_alert_rejects_normal_user(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    alert_id = _seed_event_and_alert(db)
    with pytest.raises(HTTPException) as excinfo:
        thalos_resolve_alert(alert_id, current_user=user, db=db)
    assert excinfo.value.status_code == 403
    # No debe haberse resuelto la alerta ajena por el intento rechazado.
    row = db.query(ThalosAlert).filter(ThalosAlert.id == alert_id).first()
    assert row.resolved is False


def test_thalos_legacy_resolve_alert_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    alert_id = _seed_event_and_alert(db)
    result = thalos_resolve_alert(alert_id, current_user=admin, db=db)
    assert result is not None
    row = db.query(ThalosAlert).filter(ThalosAlert.id == alert_id).first()
    assert row.resolved is True


def test_thalos_legacy_audit_rejects_normal_user(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    with pytest.raises(HTTPException) as excinfo:
        thalos_audit(current_user=user, db=db)
    assert excinfo.value.status_code == 403


def test_thalos_legacy_audit_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    result = thalos_audit(current_user=admin, db=db)
    assert result is not None


def test_thalos_legacy_monitor_rejects_normal_user(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    with pytest.raises(HTTPException) as excinfo:
        thalos_monitor_now(current_user=user, db=db)
    assert excinfo.value.status_code == 403


def test_thalos_legacy_monitor_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    result = thalos_monitor_now(current_user=admin, db=db)
    assert result is not None


def test_thalos_legacy_ingest_logs_rejects_normal_user(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    body = LogIngestBody(logs=["failed login for admin"])
    with pytest.raises(HTTPException) as excinfo:
        thalos_ingest_logs(body, current_user=user, db=db)
    assert excinfo.value.status_code == 403


def test_thalos_legacy_ingest_logs_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    body = LogIngestBody(logs=["unauthorized access attempt detected"])
    result = thalos_ingest_logs(body, current_user=admin, db=db)
    assert result is not None


# ---------------------------------------------------------------------------
# 2) thalos_v1.py — events / alerts (Vuelta 5) + status (hallazgo nuevo)
# ---------------------------------------------------------------------------


def test_thalos_v1_events_rejects_normal_user(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    with pytest.raises(HTTPException) as excinfo:
        thalos_v1_events(current_user=user, db=db)
    assert excinfo.value.status_code == 403


def test_thalos_v1_events_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    _seed_event_and_alert(db)
    result = thalos_v1_events(current_user=admin, db=db)
    assert result is not None


def test_thalos_v1_alerts_rejects_normal_user(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    with pytest.raises(HTTPException) as excinfo:
        thalos_v1_alerts(current_user=user, db=db)
    assert excinfo.value.status_code == 403


def test_thalos_v1_alerts_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    _seed_event_and_alert(db)
    result = thalos_v1_alerts(current_user=admin, db=db)
    assert result is not None


def test_thalos_v1_status_rejects_normal_user_hallazgo_nuevo(db: Session):
    """Hallazgo nuevo de la Vuelta 5 (sección 13): GET /thalos/v1/status
    incrusta audit_from_db() bajo 'database' sin ningún gate previo."""
    user, _ = _seed_company(db, is_superuser=False)
    with pytest.raises(HTTPException) as excinfo:
        thalos_v1_status(current_user=user)
    assert excinfo.value.status_code == 403


def test_thalos_v1_status_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    result = thalos_v1_status(current_user=admin)
    assert result is not None


# ---------------------------------------------------------------------------
# 3) workspaces.py::workspace_thalos_threat (Vuelta 5)
# ---------------------------------------------------------------------------


def test_workspace_thalos_threat_rejects_normal_user_and_never_leaks(db: Session):
    attacker, _ = _seed_company(db, is_superuser=False)
    request = ThalosThreatRequest(events=[])
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(workspace_thalos_threat(request, current_user=attacker, db=db))
    assert excinfo.value.status_code == 403


def test_workspace_thalos_threat_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    _seed_event_and_alert(db)
    request = ThalosThreatRequest(events=[])
    response = asyncio.run(workspace_thalos_threat(request, current_user=admin, db=db))
    assert response is not None


# ---------------------------------------------------------------------------
# 4) Hallazgo nuevo — services/automation/handlers/thalos_v1.py re-verifica
#    superusuario porque se ejecuta fuera de una petición HTTP (disparado por
#    AgentAutomationExecutor sobre cualquier AgentActivity pending)
# ---------------------------------------------------------------------------


def _make_pending_activity(db: Session, *, agent_name: str, action_type: str, user_email, details=None) -> AgentActivity:
    row = AgentActivity(
        agent_name=agent_name,
        action_type=action_type,
        action_description="vuelta5 async engine test",
        details=details or {},
        user_email=user_email,
        status="pending",
        priority="normal",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_handle_thalos_v1_detect_blocks_normal_user_email(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    activity = _make_pending_activity(
        db, agent_name="THALOS", action_type="detect_suspicious_activity", user_email=user.email
    )
    result = handle_thalos_v1_detect(activity)
    assert result["status"] == "blocked"
    assert result["details_update"]["thalos_v1"]["reason"] == "superuser_required_for_global_audit"


def test_handle_thalos_v1_detect_blocks_missing_email():
    """Simula una actividad creada sin atribución de usuario fiable (p.ej. si
    en el futuro alguna otra vía deja user_email vacío) — debe fallar cerrado,
    no abierto."""
    fake = AgentActivity(
        agent_name="THALOS",
        action_type="detect_suspicious_activity",
        action_description="sin email",
        details={},
        user_email=None,
        status="pending",
        priority="normal",
    )
    result = handle_thalos_v1_detect(fake)
    assert result["status"] == "blocked"


def test_handle_thalos_v1_detect_passes_gate_for_real_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    activity = _make_pending_activity(
        db, agent_name="THALOS", action_type="detect_suspicious_activity", user_email=admin.email
    )
    result = handle_thalos_v1_detect(activity)
    # No debe ser el bloqueo nuevo de esta vuelta; con flags por defecto
    # (THALOS_EXECUTION_ENABLED=False) el motor real responde "skipped", que
    # es un motivo DISTINTO y preexistente al de este gate.
    assert result["details_update"]["thalos_v1"]["reason"] == "THALOS_EXECUTION_ENABLED is false"


def test_handle_thalos_v1_monitor_blocks_normal_user_email(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    activity = _make_pending_activity(
        db, agent_name="THALOS", action_type="security_monitor", user_email=user.email
    )
    result = handle_thalos_v1_monitor(activity)
    assert result["status"] == "blocked"
    assert result["details_update"]["thalos_v1"]["reason"] == "superuser_required_for_global_audit"


def test_handle_thalos_v1_monitor_passes_gate_for_real_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    activity = _make_pending_activity(
        db, agent_name="THALOS", action_type="security_monitor", user_email=admin.email
    )
    result = handle_thalos_v1_monitor(activity)
    assert result is not None
    assert result.get("status") != "blocked"


def test_handle_thalos_v1_block_blocks_normal_user_email_even_with_real_victim(db: Session):
    """Reproduce el escenario más grave identificado en la Vuelta 5: un
    usuario NO superusuario no puede usar esta vía asíncrona para intentar
    bloquear a un usuario de otra empresa."""
    attacker, _ = _seed_company(db, is_superuser=False)
    victim, victim_company = _seed_company(db, is_superuser=False)
    activity = _make_pending_activity(
        db,
        agent_name="THALOS",
        action_type="block_user",
        user_email=attacker.email,
        details={"user_email": victim.email, "company_id": victim_company.id},
    )
    result = handle_thalos_v1_block(activity)
    assert result["status"] == "blocked"
    assert result["details_update"]["thalos_v1"]["reason"] == "superuser_required_for_global_audit"
    db.refresh(victim)
    assert victim.is_active is True


def test_handle_thalos_v1_block_passes_gate_for_real_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    victim, _ = _seed_company(db, is_superuser=False)
    activity = _make_pending_activity(
        db,
        agent_name="THALOS",
        action_type="block_user",
        user_email=admin.email,
        details={"user_email": victim.email},
    )
    result = handle_thalos_v1_block(activity)
    # Con THALOS_EXECUTION_ENABLED=False por defecto, el motor real responde
    # "skipped" (no ejecuta el bloqueo) -- pero confirma que pasó el gate de
    # esta vuelta, no el bloqueo nuevo.
    assert result["details_update"]["thalos_v1"]["reason"] == "THALOS_EXECUTION_ENABLED is false"


# ---------------------------------------------------------------------------
# 5) Hallazgo nuevo — POST /api/v1/activities/log sin autenticación
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _register_and_login(client: TestClient):
    suf = uuid.uuid4().hex[:10]
    payload = {
        "email": f"v5_activities_{suf}@example.com",
        "password": "TestPass1",
        "full_name": "Vuelta5 Activities Tester",
        "phone": "612345678",
        "company_name": f"Vuelta5 Activities Co {suf}",
        "business_type": "restaurant",
    }
    r = client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
    if r.status_code != 201:
        pytest.skip(f"Registro no disponible en este entorno: {r.status_code} {r.text[:200]}")
    login = client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"username": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200
    token = login.json().get("access_token")
    assert token
    return payload["email"], token


def test_log_activity_requires_authentication(client: TestClient):
    """Hallazgo nuevo de la Vuelta 5 (sección 13): antes de este fix, este
    endpoint no exigía NINGUNA autenticación."""
    r = client.post(
        f"{settings.API_V1_STR}/activities/log",
        json={
            "agent_name": "THALOS",
            "action_type": f"v5_unauth_probe_{uuid.uuid4().hex[:8]}",
            "action_description": "intento sin token",
        },
    )
    assert r.status_code in (401, 403)


def test_log_activity_ignores_client_supplied_user_email(client: TestClient, db: Session):
    """Hallazgo nuevo de la Vuelta 5: el cliente podía spoofear `user_email`
    con el email de OTRO usuario (p.ej. un superusuario conocido). Ahora debe
    ignorarse y usar siempre el email del usuario autenticado real."""
    real_email, token = _register_and_login(client)
    action_type = f"v5_spoof_probe_{uuid.uuid4().hex[:8]}"

    r = client.post(
        f"{settings.API_V1_STR}/activities/log",
        json={
            "agent_name": "THALOS",
            "action_type": action_type,
            "action_description": "intento de spoof de user_email",
            "user_email": "marketingdigitalper.seo@gmail.com",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    activity_id = r.json()["activity_id"]

    row = db.query(AgentActivity).filter(AgentActivity.id == activity_id).first()
    assert row is not None
    assert row.user_email == real_email
    assert row.user_email != "marketingdigitalper.seo@gmail.com"
