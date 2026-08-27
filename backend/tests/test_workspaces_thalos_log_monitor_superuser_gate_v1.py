"""
Vuelta 4 de AUDIT_FIX_THALOS_SHIELD.md (sección 10.2/10.3): la ronda 3 de
revisión independiente confirmó en vivo, con una cuenta 100% nueva y sin
ninguna precondición (sin flags, sin superusuario, sin monkeypatch), que
`POST /api/v1/workspaces/thalos/log-monitor`
(`app/api/v1/endpoints/workspaces.py::workspace_thalos_logs`) invoca
`thalos_security_engine.scan_logs` de forma incondicional y persiste el
resultado (incluyendo `failed_login_candidates`/`pattern_alerts` de OTRAS
empresas) en el workspace del propio tenant llamante. Es la misma clase de
fuga que ya motivó el gate de superusuario aplicado en la Vuelta 3 a
`THALOS.SCAN` (`zeus_core.py`) y `detect_suspicious_activity`
(`thalos_v1.py`), alcanzada aquí por una ruta distinta.

Estos tests reproducen exactamente el escenario del revisor (tenant nuevo sin
actividad propia, cero flags THALOS_* activados) contra el código corregido:
un usuario normal debe recibir 403 antes de que `scan_logs` se ejecute
siquiera, y un superusuario debe poder seguir usando el endpoint con datos
reales. También cubre, por consistencia, el mismo gate aplicado a
`GET /thalos/v1/audit` y `POST /thalos/v1/monitor`.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest  # pyright: ignore[reportMissingImports]
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.thalos_v1 import (
    ThalosMonitorRequest,
    thalos_v1_audit,
    thalos_v1_monitor,
)
from app.api.v1.endpoints.workspaces import ThalosLogRequest, workspace_thalos_logs
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.thalos_security_event import ThalosLoginAttempt
from app.models.thalos_workspace_item import ThalosWorkspaceItem
from app.models.user import User


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
        email=f"v4_log_monitor_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Vuelta4 LogMonitor Tester",
        is_active=True,
        is_superuser=is_superuser,
    )
    company = Company(company_name=f"Vuelta4 Co {suf}", slug=f"v4-log-monitor-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    return user, company


def _seed_other_tenant_brute_force(db: Session) -> str:
    """Siembra >=5 intentos fallidos de un email que NO pertenece a ninguna
    empresa del tenant que hará la llamada — simula datos reales de OTRA
    empresa/sesión, exactamente el escenario reproducido por el revisor."""
    victim_email = f"brute_other_tenant_{uuid.uuid4().hex[:8]}@evil.test"
    now = datetime.now(timezone.utc)
    for _ in range(6):
        db.add(
            ThalosLoginAttempt(
                email=victim_email,
                ip_address="203.0.113.9",
                success=0,
                created_at=now - timedelta(minutes=1),
            )
        )
    db.commit()
    return victim_email


def test_workspace_log_monitor_rejects_normal_user_and_never_leaks(db: Session):
    """Reproduce exactamente el escenario del revisor: tenant nuevo sin
    actividad propia, cero flags activados, llamada HTTP ordinaria."""
    attacker, _ = _seed_company(db, is_superuser=False)
    other_tenant_email = _seed_other_tenant_brute_force(db)

    request = ThalosLogRequest(logs=[])
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(workspace_thalos_logs(request, current_user=attacker, db=db))

    assert excinfo.value.status_code == 403

    # El rechazo debe ocurrir ANTES de invocar scan_logs: no debe haberse
    # persistido ningún ThalosWorkspaceItem para este usuario (antes del fix,
    # el escaneo cross-tenant se persistía siempre, incluso con logs=[]).
    items = (
        db.query(ThalosWorkspaceItem)
        .filter(ThalosWorkspaceItem.user_id == attacker.id)
        .all()
    )
    assert items == []
    # Control: el email de la otra empresa sigue existiendo en la tabla
    # global (no se borró), simplemente el atacante no pudo verlo.
    assert (
        db.query(ThalosLoginAttempt)
        .filter(ThalosLoginAttempt.email == other_tenant_email)
        .count()
        == 6
    )


def test_workspace_log_monitor_allows_superuser_with_real_scan(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    other_tenant_email = _seed_other_tenant_brute_force(db)

    request = ThalosLogRequest(logs=[])
    response = asyncio.run(workspace_thalos_logs(request, current_user=admin, db=db))

    # No debe lanzar HTTPException; el superusuario sí puede ejecutar el
    # escaneo real (mitigación interina, no una prohibición total).
    assert response.get("success") is True

    # El escaneo real se persiste en el ThalosWorkspaceItem del usuario (no
    # va embebido en la respuesta HTTP directa), tal como reprodujo el
    # revisor: GET /thalos/v1/workspace/items lo expone después.
    items = (
        db.query(ThalosWorkspaceItem)
        .filter(ThalosWorkspaceItem.user_id == admin.id)
        .all()
    )
    assert len(items) == 1
    payload = json.loads(items[0].payload_json or "{}")
    real_scan = payload.get("real_scan") or {}
    candidates = [c["email"] for c in real_scan.get("failed_login_candidates", [])]
    assert other_tenant_email in candidates


def test_thalos_v1_audit_rejects_normal_user(db: Session):
    user, _ = _seed_company(db, is_superuser=False)

    with pytest.raises(HTTPException) as excinfo:
        thalos_v1_audit(current_user=user, db=db)

    assert excinfo.value.status_code == 403


def test_thalos_v1_audit_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)

    result = thalos_v1_audit(current_user=admin, db=db)

    assert "data" in result or "event_count" in str(result)


def test_thalos_v1_monitor_rejects_normal_user(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    body = ThalosMonitorRequest()

    with pytest.raises(HTTPException) as excinfo:
        thalos_v1_monitor(body, current_user=user, db=db)

    assert excinfo.value.status_code == 403


def test_thalos_v1_monitor_allows_superuser(db: Session):
    admin, _ = _seed_company(db, is_superuser=True)
    body = ThalosMonitorRequest()

    result = thalos_v1_monitor(body, current_user=admin, db=db)

    # No debe ser el 403 nuevo; debe llegar al motor real (flags por defecto
    # en false => monitoring_enabled False, pero eso es un comportamiento
    # distinto y preexistente, no la mitigación de esta vuelta).
    assert result is not None
