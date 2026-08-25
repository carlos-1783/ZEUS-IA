"""
Tests del fix de THALOS.SHIELD/SCAN/BLOCK en la capa legacy stub
(app/core/zeus_agents.py), ver AUDIT_FIX_THALOS_SHIELD.md.

Antes del fix, estos comandos devolvían datos 100% hardcodeados
("threats_blocked": 0, "encryption_status": "activo" fijos,
"blocked_ips": ["192.168.1.100", "10.0.0.50"] fijas ignorando `data`) y el
endpoint /api/v1/zeus/execute no filtraba por tenant. Estos tests fallan si
alguien reintroduce esa simulación.
"""

from __future__ import annotations

import uuid

import pytest  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.core.zeus_agents import zeus_manager
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User


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
        email=f"thalos_shield_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Thalos Shield Tester",
        is_active=True,
    )
    company = Company(company_name=f"Thalos Shield Co {suf}", slug=f"thalos-shield-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    return user, company


def test_shield_without_db_context_declares_not_simulated_data():
    """Sin sesión de BD inyectada, SHIELD debe declararlo, no inventar cifras."""
    result = zeus_manager.execute_zeus_command("THALOS.SHIELD", {})
    data = result["data"]
    assert data["threats_blocked"] == "no_disponible"
    assert data["threats_blocked_source"] == "sin_sesion_bd"
    # encryption_status/jwt_oauth2 ya no son literales fijos: deben venir de
    # una de las categorías reales conocidas.
    assert data["encryption_status"] in (
        "activo",
        "fallback_dev_no_valido_para_produccion",
        "no_configurado",
    )
    assert data["jwt_oauth2"] in ("configurado", "clave_por_defecto_no_apta_produccion")


def test_shield_threats_blocked_is_tenant_isolated(db: Session):
    """Dos tenants distintos no deben ver los mismos threats_blocked reales."""
    _, company_a = _seed_company(db)
    _, company_b = _seed_company(db)

    db.add(
        ThalosSecurityEvent(
            event_type="action_block_user",
            severity="info",
            source="test",
            company_id=company_a.id,
            action_taken="block_user",
            details_json="{}",
        )
    )
    db.commit()

    result_a = zeus_manager.execute_zeus_command(
        "THALOS.SHIELD", {}, db=db, company_id=company_a.id
    )
    result_b = zeus_manager.execute_zeus_command(
        "THALOS.SHIELD", {}, db=db, company_id=company_b.id
    )

    assert result_a["data"]["threats_blocked"] == 1
    assert result_b["data"]["threats_blocked"] == 0
    assert result_a["data"]["company_id_scope"] == company_a.id
    assert result_b["data"]["company_id_scope"] == company_b.id

    # El singleton THALOS no debe quedar con contexto de un tenant filtrado
    # tras la llamada (se limpia en ZeusAgentManager.execute_zeus_command).
    from app.core.zeus_agents import AgentType

    thalos_agent = zeus_manager.agents[AgentType.THALOS]
    assert thalos_agent.db is None
    assert thalos_agent.company_id is None


def test_scan_delegates_to_real_security_engine(db: Session):
    result = zeus_manager.execute_zeus_command("THALOS.SCAN", {"hours": 24}, db=db)
    assert result["status"] == "success"
    assert result["data"]["source"] == "thalos_security_engine.scan_logs"
    assert isinstance(result["data"]["vulnerabilities_found"], int)


def test_scan_without_db_is_honest_error():
    result = zeus_manager.execute_zeus_command("THALOS.SCAN", {})
    assert result["status"] == "error"
    assert result["data"]["scan_result"] == "no_disponible"


def test_block_never_returns_fake_fixed_ips(db: Session):
    """Regresión directa del hallazgo: BLOCK ya no devuelve
    ["192.168.1.100", "10.0.0.50"] fijas ignorando `data`."""
    result_no_email = zeus_manager.execute_zeus_command("THALOS.BLOCK", {}, db=db)
    assert result_no_email["data"]["blocked_ips"] == []
    assert result_no_email["status"] != "success"

    result_with_ip = zeus_manager.execute_zeus_command(
        "THALOS.BLOCK", {"ip": "203.0.113.5"}, db=db
    )
    assert result_with_ip["data"]["blocked_ips"] == []
    assert result_with_ip["status"] == "not_implemented"
    assert result_with_ip["data"]["requested_ip"] == "203.0.113.5"


def test_block_with_email_respects_real_execution_flags(db: Session):
    """Con flags reales desactivados (default), BLOCK no debe fingir éxito."""
    from app.core.config import settings

    assert settings.THALOS_EXECUTION_ENABLED is False

    user, company = _seed_company(db)
    result = zeus_manager.execute_zeus_command(
        "THALOS.BLOCK",
        {"user_email": user.email},
        db=db,
        company_id=company.id,
    )
    assert result["data"]["executed"] is False
    assert result["data"]["source"] == "thalos_executor.block_user"
