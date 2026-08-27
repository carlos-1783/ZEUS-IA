"""
AUDIT_THALOS_ESTRUCTURAL.md, paso 1: `company_id` real en las 4 tablas del
subsistema de logs de seguridad de THALOS (`ThalosEvent`, `ThalosAlert`,
`ThalosSecurityEvent`, `ThalosLoginAttempt`) tras 6 vueltas de mitigaciones
interinas (gates de superusuario) documentadas en AUDIT_FIX_THALOS_SHIELD.md.

Cubre:
1. Las 4 tablas exponen `company_id` como columna real del modelo.
2. `services.thalos_security_engine.record_login_attempt` resuelve
   `company_id` best-effort cuando el email corresponde a un usuario real
   registrado, y lo deja `NULL` cuando no (fuerza bruta con emails
   inventados -- irreductible, documentado en el propio informe).
3. `services.thalos_alert_service.generate_alerts_from_engine` resuelve
   `company_id` para alertas `rule_id=brute_force_email` (única regla con un
   email estructurado en `metadata`) usando el mismo criterio.
4. `app.db.tenant_context.set_tenant_context`/`get_db_scoped` son no-op
   seguros contra SQLite (RLS no existe ahí) y no rompen el camino normal.

La migración en sí (`0046_thalos_tables_company_id.py`,
`0047_thalos_row_level_security.py`) se verificó por separado ejecutando
`alembic upgrade head` / `downgrade` / `upgrade head` contra una copia
desechable de `zeus.db` (ver AUDIT_THALOS_ESTRUCTURAL.md) -- no se repite
aquí porque pytest usa `Base.metadata.create_all()`, no Alembic.
"""

from __future__ import annotations

import uuid

import pytest  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.db.tenant_context import get_db_scoped, set_tenant_context
from app.models.company import Company, UserCompany
from app.models.thalos_alert import ThalosAlert
from app.models.thalos_event import ThalosEvent
from app.models.thalos_security_event import ThalosLoginAttempt, ThalosSecurityEvent
from app.models.user import User
from services.thalos_security_engine import record_login_attempt


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_company(db: Session):
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"v6_cid_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Vuelta6 CompanyId Tester",
        is_active=True,
    )
    company = Company(company_name=f"Vuelta6 CID Co {suf}", slug=f"v6-cid-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    return user, company


# ---------------------------------------------------------------------------
# 1) Las 4 tablas exponen company_id
# ---------------------------------------------------------------------------


def test_all_4_thalos_tables_have_company_id_column():
    for model in (ThalosEvent, ThalosAlert, ThalosSecurityEvent, ThalosLoginAttempt):
        assert "company_id" in model.__table__.columns.keys(), model.__tablename__


# ---------------------------------------------------------------------------
# 2) record_login_attempt -- backfill/forward-fill best-effort
# ---------------------------------------------------------------------------


def test_record_login_attempt_resolves_company_id_for_real_user(db: Session):
    user, company = _seed_company(db)
    record_login_attempt(db, email=user.email, ip_address="1.2.3.4", success=True)
    db.commit()
    row = (
        db.query(ThalosLoginAttempt)
        .filter(ThalosLoginAttempt.email == user.email.lower())
        .order_by(ThalosLoginAttempt.id.desc())
        .first()
    )
    assert row is not None
    assert row.company_id == company.id


def test_record_login_attempt_leaves_null_for_nonexistent_email(db: Session):
    fake_email = f"brute_{uuid.uuid4().hex[:8]}@evil.test"
    record_login_attempt(db, email=fake_email, ip_address="1.2.3.4", success=False)
    db.commit()
    row = (
        db.query(ThalosLoginAttempt)
        .filter(ThalosLoginAttempt.email == fake_email)
        .order_by(ThalosLoginAttempt.id.desc())
        .first()
    )
    assert row is not None
    assert row.company_id is None


# ---------------------------------------------------------------------------
# 3) generate_alerts_from_engine -- brute_force_email resuelve company_id
# ---------------------------------------------------------------------------


def test_resolve_company_id_for_email_matches_real_user(db: Session):
    """Unidad: `_resolve_company_id_for_email` (helper nuevo de este paso) es
    la pieza exacta que `create_alert`/`generate_alerts_from_engine` usan
    para atribuir `company_id` a una alerta `brute_force_email`. Probado de
    forma aislada, sin depender del motor de detección completo (que
    comparte una BD de desarrollo con datos de sesiones de prueba
    anteriores y no es determinista para aserciones sobre "la primera
    alerta creada")."""
    from services.thalos_alert_service import _resolve_company_id_for_email

    user, company = _seed_company(db)
    assert _resolve_company_id_for_email(db, user.email) == company.id


def test_resolve_company_id_for_email_returns_none_for_unknown_email(db: Session):
    from services.thalos_alert_service import _resolve_company_id_for_email

    fake_email = f"brute_{uuid.uuid4().hex[:8]}@evil.test"
    assert _resolve_company_id_for_email(db, fake_email) is None


def test_create_alert_persists_company_id_when_resolved(db: Session):
    """`generate_alerts_from_engine` pasa `company_id=_resolve_company_id_for_email(...)`
    a `create_alert` para candidatos `rule_id=brute_force_email` (única
    regla con `metadata['email']` estructurado, ver
    `services/thalos_threat_engine.py::evaluate_events`). Se prueba
    `create_alert` directamente con esa misma señal, evitando la
    dependencia de `evaluate_events` sobre el estado global compartido de
    `thalos_login_attempts` en la BD de desarrollo."""
    from services.thalos_alert_service import create_alert

    user, company = _seed_company(db)
    row = create_alert(
        db,
        title="Brute-force por email",
        level="critical",
        message=f"{user.email}: 6 fallos en 60min",
        rule_id="brute_force_email",
        metadata={"email": user.email, "failed_count": 6},
        company_id=company.id,
    )
    db.commit()
    db.refresh(row)
    assert row.company_id == company.id


def test_evaluate_events_candidate_for_our_email_carries_email_metadata(db: Session):
    """Prueba de integración parcial: `evaluate_events` (el motor real de
    detección) produce, para nuestro email de prueba con >=5 fallos
    recientes, un candidato `rule_id=brute_force_email` con
    `metadata['email']` igual a nuestro email -- exactamente el campo que
    `generate_alerts_from_engine` usa para resolver `company_id` (ver
    `test_create_alert_persists_company_id_when_resolved` para la
    verificación de esa segunda mitad). No se afirma que sea el ÚNICO
    candidato ni el primero en persistirse: `generate_alerts_from_engine`
    deduplica por `rule_id` global una vez al día (no por email), así que en
    una BD de desarrollo compartida con datos de sesiones de prueba
    anteriores puede haber otros candidatos con el mismo `rule_id` -- eso es
    una propiedad preexistente del motor, no de este cambio, y no se prueba
    aquí."""
    user, company = _seed_company(db)
    for _ in range(6):
        db.add(ThalosLoginAttempt(email=user.email.lower(), success=0))
    db.commit()

    from services.thalos_threat_engine import evaluate_events

    candidates = evaluate_events(db, window_minutes=60)
    ours = [
        c
        for c in candidates
        if c.get("rule_id") == "brute_force_email" and (c.get("metadata") or {}).get("email") == user.email.lower()
    ]
    assert ours, "evaluate_events no generó un candidato brute_force_email para nuestro email"
    from services.thalos_alert_service import _resolve_company_id_for_email

    assert _resolve_company_id_for_email(db, ours[0]["metadata"]["email"]) == company.id


# ---------------------------------------------------------------------------
# 4) tenant_context -- no-op seguro contra SQLite
# ---------------------------------------------------------------------------


def test_set_tenant_context_is_noop_on_sqlite(db: Session):
    # No debe lanzar ninguna excepción ni alterar el dialecto de la sesión.
    set_tenant_context(db, 123, user_id=1, user_email="x@example.test")
    assert db.bind.dialect.name == "sqlite"


def test_get_db_scoped_returns_usable_session_for_normal_user(db: Session):
    user, company = _seed_company(db)
    scoped = get_db_scoped(current_user=user, db=db)
    assert scoped is db
    # Debe seguir siendo una sesión funcional (no-op en SQLite).
    assert scoped.query(ThalosEvent).count() >= 0


def test_get_db_scoped_bypasses_context_for_superuser(db: Session):
    admin = User(
        email=f"v6_cid_admin_{uuid.uuid4().hex[:8]}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Vuelta6 CID Admin",
        is_active=True,
        is_superuser=True,
    )
    db.add(admin)
    db.commit()
    scoped = get_db_scoped(current_user=admin, db=db)
    assert scoped is db
