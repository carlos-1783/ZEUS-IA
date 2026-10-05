"""Aislamiento de verticales: ninguna empresa debe ver/usar un módulo que no
tiene contratado solo porque está autenticada.

Contexto (hallazgo A, confirmado por dos auditorías independientes): antes
de `app.core.module_access.require_module`, CUALQUIER empresa autenticada
(restaurante, tienda, oficina...) podía golpear `/api/v1/insurance/*` y
crear pólizas/siniestros reales, aunque el filtrado por `company_id` dentro
de esos endpoints SÍ fuera correcto (sin fuga de datos entre empresas que
ya habían entrado). No había ningún `require_module` en todo el backend
(confirmado por grep). Este fichero fija dos cosas:

1. Test de guardia (estructural): todo módulo en
   `app.core.verticals_registry.VERTICAL_MODULE_COMPANY_TYPES` tiene un
   router real montado en su prefijo, y TODAS sus rutas llevan de verdad
   `require_module(<ese módulo>)` como dependencia. Si alguien quita el
   `require_module` del router de Seguros (o de cualquier vertical futura)
   por error, este test falla.
2. Test de regresión HTTP real: usuario normal de una empresa cualquiera
   (no superusuario, `company_type` no autorizado) -> 403 en
   `/api/v1/insurance/policies`. Superusuario -> 200 (sigue pudiendo
   administrar/probar la vertical aunque Carlos no haya confirmado todavía
   qué `company_type` la tendrán contratada).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.core.security import get_password_hash
from app.core.verticals_registry import (
    VERTICAL_MODULE_COMPANY_TYPES,
    VERTICAL_MODULE_ROUTE_PREFIXES,
)
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.user import User


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    """TestClient sin lifespan completo (coherente con el resto de la suite
    de aislamiento: no dispara los eventos de arranque de la app)."""
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def _seed_user_with_company(db: Session, *, company_type: str | None, tag: str) -> User:
    suf = uuid.uuid4().hex[:8]
    company = Company(
        company_name=f"Vertical Test Co {tag} {suf}",
        slug=f"vertical-test-{tag}-{suf}",
        company_type=company_type,
    )
    db.add(company)
    db.flush()

    user = User(
        email=f"vertical_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"Vertical Test {tag}",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()

    db.add(UserCompany(user_id=user.id, company_id=company.id, role="company_admin"))
    db.commit()
    db.refresh(user)
    return user


def _superuser(db: Session, *, tag: str = "su") -> User:
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"vertical_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"Vertical Superuser {tag}",
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --------------------------------------------------------------------- guardia


def _routes_under_prefix(prefix: str):
    full_prefix = f"{settings.API_V1_STR}{prefix}"
    return [r for r in app.routes if getattr(r, "path", "").startswith(full_prefix)]


@pytest.mark.parametrize("module", sorted(VERTICAL_MODULE_COMPANY_TYPES.keys()))
def test_every_registered_vertical_has_a_mounted_router(module: str):
    """Si el registro declara un módulo, debe existir un router real montado
    en su prefijo (si esto falla, o el registro quedó huérfano, o alguien
    desmontó el router sin limpiar el registro)."""
    prefix = VERTICAL_MODULE_ROUTE_PREFIXES.get(module)
    assert prefix, f"Falta VERTICAL_MODULE_ROUTE_PREFIXES['{module}'] para el módulo registrado '{module}'"

    routes = _routes_under_prefix(prefix)
    assert routes, f"No hay ninguna ruta montada bajo '{settings.API_V1_STR}{prefix}' para el módulo '{module}'"


@pytest.mark.parametrize("module", sorted(VERTICAL_MODULE_COMPANY_TYPES.keys()))
def test_every_route_of_a_registered_vertical_requires_its_module(module: str):
    """Cada ruta del router de la vertical debe llevar de verdad
    `require_module(<module>)` en su cadena de dependencias (no solo
    `get_current_active_user`). Falla hoy si alguien quita el
    `dependencies=[Depends(require_module(...))]` del router por error."""
    prefix = VERTICAL_MODULE_ROUTE_PREFIXES[module]
    routes = _routes_under_prefix(prefix)
    assert routes, f"No hay rutas que comprobar para '{module}' (ver test anterior)"

    for route in routes:
        dependant = route.dependant
        markers = {
            getattr(dep.call, "__module_access__", None) for dep in dependant.dependencies
        }
        assert module in markers, (
            f"La ruta {route.path} ({getattr(route, 'methods', None)}) no tiene "
            f"require_module('{module}') aplicado -- markers encontrados: {markers}"
        )


def test_registry_has_no_module_without_route_prefix():
    """Lo inverso: toda clave de VERTICAL_MODULE_COMPANY_TYPES debe tener su
    prefijo de ruta declarado -- evita un registro con entradas 'fantasma'."""
    missing = sorted(set(VERTICAL_MODULE_COMPANY_TYPES) - set(VERTICAL_MODULE_ROUTE_PREFIXES))
    assert not missing, f"Módulos registrados sin VERTICAL_MODULE_ROUTE_PREFIXES: {missing}"


# --------------------------------------------------------------------- insurance (HTTP real)


def test_insurance_policies_requires_authentication(client: TestClient):
    resp = client.get(f"{settings.API_V1_STR}/insurance/policies")
    assert resp.status_code == 401


def test_insurance_policies_forbidden_for_regular_company_without_module(client: TestClient, db: Session):
    """Empresa cualquiera (sin company_type autorizado para 'insurance',
    hoy ninguno lo está salvo decisión futura de Carlos) -> 403 real, no
    fuga de datos ni 500 opaco."""
    user = _seed_user_with_company(db, company_type="bar_restaurant", tag="rest")
    app.dependency_overrides[get_current_active_user] = lambda: user

    resp = client.get(f"{settings.API_V1_STR}/insurance/policies")
    assert resp.status_code == 403
    assert "insurance" in resp.json()["detail"]


def test_insurance_policies_forbidden_for_company_without_type(client: TestClient, db: Session):
    """Empresa sin company_type asignado (NULL) tampoco debe entrar."""
    user = _seed_user_with_company(db, company_type=None, tag="notype")
    app.dependency_overrides[get_current_active_user] = lambda: user

    resp = client.get(f"{settings.API_V1_STR}/insurance/policies")
    assert resp.status_code == 403


def test_insurance_policies_ok_for_superuser(client: TestClient, db: Session):
    """Superusuario conserva acceso (bypass explícito), independientemente
    del registro -- necesario para que el equipo pueda seguir probando la
    vertical mientras Carlos confirma los company_type reales."""
    user = _superuser(db)
    app.dependency_overrides[get_current_active_user] = lambda: user

    resp = client.get(f"{settings.API_V1_STR}/insurance/policies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


def test_require_module_dependency_denies_unknown_module(client: TestClient, db: Session):
    """Un módulo no registrado en absoluto se trata como cerrado (fail-closed),
    nunca como abierto por defecto."""
    from app.core.module_access import _user_has_module_access

    user = _seed_user_with_company(db, company_type="bar_restaurant", tag="unknown")
    assert _user_has_module_access(db, user, "modulo_que_no_existe") is False
