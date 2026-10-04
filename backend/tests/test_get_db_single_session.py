"""
E5 — Regresión: una sola sesión SQLAlchemy por request.

Causa raíz exacta (documentada en el backlog y ya diagnosticada para el caso
puntual de onboarding en el commit `038096f`): `app.core.auth` importaba
`get_db` desde `app.db.base` (un wrapper que delega en `app.db.session.get_db`
vía `yield from`, pero que es un objeto función DISTINTO), mientras que los
endpoints propios (`app/api/v1/endpoints/*.py`) importan `get_db` desde
`app.db.session` directamente.

FastAPI cachea dependencias DENTRO de una misma request por identidad de
función: `Dependant.cache_key = (self.call, scopes)`
(`fastapi/dependencies/models.py`). Dos callables distintos -aunque
funcionalmente equivalentes- nunca se deduplican. Así que cualquier endpoint
que combine `current_user: User = Depends(get_current_active_user)` (que
internamente depende de `get_db`) con su propio
`db: Session = Depends(get_db)` acababa creando DOS `SessionLocal()`
independientes para la misma request HTTP, si cada `get_db` venía de un
módulo distinto. Esa es la clase exacta de bug que causó el 500 de doble
sesión en `POST /onboarding/questionnaire`.

Fix aplicado (E5): `app/core/auth.py` y
`app/api/v1/endpoints/commands.py` ahora importan `get_db` desde
`app.db.session` igual que el resto de endpoints, así que
`Depends(get_current_active_user)` y `Depends(get_db)` propio del endpoint
comparten el MISMO callable y FastAPI los deduplica dentro de la request.

Este test no asume el fix por lectura de código: instrumenta
`SessionLocal()` (contando invocaciones reales vía monkeypatch) durante una
request real autenticada a `GET /onboarding/status` -- que usa exactamente
este patrón (`get_current_active_user` + `db` propio) -- y confirma que se
crea UNA sola sesión SQLAlchemy, no dos.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

import app.db.session as session_module
from app.core.config import settings
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _register_and_login(client: TestClient) -> str:
    suf = uuid.uuid4().hex[:10]
    payload = {
        "email": f"sesunica_{suf}@example.com",
        "password": "TestPass1",
        "full_name": "Titular Sesion Unica",
        "phone": "612345678",
        "company_name": f"Empresa Sesion Unica {suf}",
        "business_type": "restaurant",
    }
    r = client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
    if r.status_code != 201:
        pytest.skip(f"Registro no disponible en este entorno: {r.status_code} {r.text[:200]}")
    login = client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"username": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def test_onboarding_status_creates_single_sqlalchemy_session(client: TestClient, monkeypatch):
    """
    GET /auth/onboarding/status usa `db: Session = Depends(get_db)` propio
    del endpoint Y `current_user: User = Depends(get_current_active_user)`
    (que a su vez depende de `get_db` dentro de `app.core.auth`). Si ambos
    `get_db` no son el mismo objeto función, FastAPI crea dos sesiones.
    """
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    real_session_local = session_module.SessionLocal
    created_sessions = []

    def counting_session_local(*args, **kwargs):
        session = real_session_local(*args, **kwargs)
        created_sessions.append(session)
        return session

    # Se parchea el nombre dentro del propio módulo session.py (que es desde
    # donde `get_db` invoca `SessionLocal()`), no un wrapper/mock del
    # comportamiento de BD: la query real sigue ejecutándose contra la BD
    # real, solo se cuenta cuántas veces se instancia la sesión.
    monkeypatch.setattr(session_module, "SessionLocal", counting_session_local)

    r = client.get(f"{settings.API_V1_STR}/auth/onboarding/status", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json().get("questionnaire_completed") is False

    assert len(created_sessions) == 1, (
        f"Se esperaba exactamente 1 sesión SQLAlchemy para esta request "
        f"(get_current_active_user y el `db` propio del endpoint deben "
        f"compartir el mismo get_db/SessionLocal), pero se crearon "
        f"{len(created_sessions)}. Esto es exactamente el patrón de bug de "
        f"doble sesión (mismo diagnosticado y corregido puntualmente para "
        f"onboarding en el commit 038096f) a nivel arquitectural."
    )


def test_tpv_invoice_endpoint_also_single_session(client: TestClient, monkeypatch):
    """
    Mismo patrón (`get_current_active_user` + `db` propio) en un endpoint
    distinto (POST /tpv/products, que requiere auth real), para confirmar
    que el fix no es específico de onboarding sino arquitectural.
    """
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    real_session_local = session_module.SessionLocal
    created_sessions = []

    def counting_session_local(*args, **kwargs):
        session = real_session_local(*args, **kwargs)
        created_sessions.append(session)
        return session

    monkeypatch.setattr(session_module, "SessionLocal", counting_session_local)

    r = client.post(
        f"{settings.API_V1_STR}/tpv/products",
        json={"name": "Producto Sesion Unica", "price": 1.0, "category": "general", "iva_rate": 21.0},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    assert len(created_sessions) == 1, (
        f"POST /tpv/products combina Depends(get_current_active_user) con su "
        f"propio Depends(get_db); se esperaba 1 sesión SQLAlchemy y se "
        f"crearon {len(created_sessions)}."
    )
