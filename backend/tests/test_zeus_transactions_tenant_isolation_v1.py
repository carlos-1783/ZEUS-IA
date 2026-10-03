"""
Regresión N2 (confirmado por dos auditorías independientes): las transacciones
del orquestador ZEUS se podían leer y EJECUTAR sin comprobar que pertenecieran
a la empresa del usuario autenticado. `zeus_transactions_v1.py` recibía
`current_user` en `GET /zeus/transactions/{id}` y lo descartaba (`_ =
current_user`); `get_transaction`/`execute_transaction` en
`zeus_transaction_system_v1.py` no comprobaban `company_id`/owner en ningún
punto. Un usuario autenticado de la empresa A podía leer o ejecutar una
transacción de la empresa B conociendo o adivinando el `transaction_id`.

Estos tests reproducen el escenario con dos empresas reales (sin mocks de
contenido) a través del endpoint HTTP real (`TestClient`, con auth real vía
`app.dependency_overrides[get_current_active_user]` -- mismo patrón que
`test_interaction_tenant_isolation_v1.py`) y también a nivel de servicio.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.user import User
from app.models.zeus_transaction import ZeusTransaction
from services.zeus_transaction_system_v1 import create_transaction, execute_transaction, get_transaction


@pytest.fixture()
def db():
    ZeusTransaction.__table__.drop(bind=engine, checkfirst=True)
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ZeusTransaction.__table__,
            User.__table__,
            Company.__table__,
            UserCompany.__table__,
        ],
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_user_with_company(db: Session, *, tag: str, superuser: bool = False) -> tuple[User, Company]:
    suf = uuid.uuid4().hex[:8]
    company = Company(company_name=f"TX Co {tag} {suf}", slug=f"tx-{tag}-{suf}")
    db.add(company)
    db.flush()
    user = User(
        email=f"tx_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"TX {tag}",
        is_active=True,
        is_superuser=superuser,
    )
    db.add(user)
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(user)
    db.refresh(company)
    return user, company


def _create_tx(db: Session, user: User) -> dict:
    with patch.dict(
        __import__("os").environ,
        {"AFRODITA_EXECUTION_ENABLED": "true", "AFRODITA_READ_ONLY_MODE": "false"},
        clear=False,
    ):
        return create_transaction(
            db,
            user,
            initiator={"type": "USER", "id": str(user.id), "source": "API"},
            context={},
            steps=[{"module": "WORKSPACE", "action": "persist_summary", "input": {"note": "secret-a"}}],
        )


# --------------------------------------------------------------------------- nivel servicio


def test_transaction_stores_creator_company_id(db: Session):
    user_a, company_a = _seed_user_with_company(db, tag="a")
    tx = _create_tx(db, user_a)
    row = db.query(ZeusTransaction).filter(ZeusTransaction.transaction_id == tx["transaction_id"]).first()
    assert row.company_id == company_a.id


def test_get_transaction_denies_other_company(db: Session):
    user_a, _ = _seed_user_with_company(db, tag="a")
    user_b, _ = _seed_user_with_company(db, tag="b")
    tx = _create_tx(db, user_a)

    # El creador sí puede leerla.
    out = get_transaction(db, user_a, tx["transaction_id"])
    assert out["transaction_id"] == tx["transaction_id"]

    # Un usuario de otra empresa NO puede leerla.
    with pytest.raises(Exception) as exc_info:
        get_transaction(db, user_b, tx["transaction_id"])
    assert getattr(exc_info.value, "status_code", None) == 403


def test_execute_transaction_denies_other_company_and_does_not_execute(db: Session):
    user_a, _ = _seed_user_with_company(db, tag="a")
    user_b, _ = _seed_user_with_company(db, tag="b")
    tx = _create_tx(db, user_a)

    with pytest.raises(Exception) as exc_info:
        execute_transaction(db, user_b, tx["transaction_id"])
    assert getattr(exc_info.value, "status_code", None) == 403

    # La transacción de A sigue PENDING -- B no logró ejecutarla.
    row = db.query(ZeusTransaction).filter(ZeusTransaction.transaction_id == tx["transaction_id"]).first()
    assert row.status == "PENDING"


def test_superuser_can_read_and_execute_any_company_transaction(db: Session):
    user_a, _ = _seed_user_with_company(db, tag="a")
    superuser, _ = _seed_user_with_company(db, tag="super", superuser=True)
    tx = _create_tx(db, user_a)

    out = get_transaction(db, superuser, tx["transaction_id"])
    assert out["transaction_id"] == tx["transaction_id"]

    with patch.dict(
        __import__("os").environ,
        {"AFRODITA_EXECUTION_ENABLED": "true", "AFRODITA_READ_ONLY_MODE": "false"},
        clear=False,
    ):
        result = execute_transaction(db, superuser, tx["transaction_id"])
    assert result["status"] == "COMMITTED"


def test_owner_can_execute_own_transaction(db: Session):
    """Regresión negativa: el fix no debe bloquear al propio dueño."""
    user_a, _ = _seed_user_with_company(db, tag="a")
    tx = _create_tx(db, user_a)
    with patch.dict(
        __import__("os").environ,
        {"AFRODITA_EXECUTION_ENABLED": "true", "AFRODITA_READ_ONLY_MODE": "false"},
        clear=False,
    ):
        result = execute_transaction(db, user_a, tx["transaction_id"])
    assert result["status"] == "COMMITTED"


# --------------------------------------------------------------------------- nivel HTTP (endpoint real)


@pytest.fixture()
def raw_client():
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def test_http_get_transaction_403_for_other_company(db: Session, raw_client: TestClient):
    user_a, _ = _seed_user_with_company(db, tag="a")
    user_b, _ = _seed_user_with_company(db, tag="b")
    tx = _create_tx(db, user_a)

    app.dependency_overrides[get_current_active_user] = lambda: user_b
    resp = raw_client.get(f"/api/v1/zeus/transactions/{tx['transaction_id']}")
    assert resp.status_code == 403


def test_http_get_transaction_200_for_owner(db: Session, raw_client: TestClient):
    user_a, _ = _seed_user_with_company(db, tag="a")
    tx = _create_tx(db, user_a)

    app.dependency_overrides[get_current_active_user] = lambda: user_a
    resp = raw_client.get(f"/api/v1/zeus/transactions/{tx['transaction_id']}")
    assert resp.status_code == 200
    assert resp.json()["transaction_id"] == tx["transaction_id"]


def test_http_execute_transaction_403_for_other_company(db: Session, raw_client: TestClient):
    user_a, _ = _seed_user_with_company(db, tag="a")
    user_b, _ = _seed_user_with_company(db, tag="b")
    tx = _create_tx(db, user_a)

    app.dependency_overrides[get_current_active_user] = lambda: user_b
    resp = raw_client.post(f"/api/v1/zeus/transactions/{tx['transaction_id']}/execute")
    assert resp.status_code == 403

    row = db.query(ZeusTransaction).filter(ZeusTransaction.transaction_id == tx["transaction_id"]).first()
    assert row.status == "PENDING"


def test_http_get_transaction_requires_auth(raw_client: TestClient):
    resp = raw_client.get("/api/v1/zeus/transactions/does-not-matter")
    assert resp.status_code == 401
