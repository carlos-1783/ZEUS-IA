"""
Regresión E1 (backlog ejecutor-produccion, auditoría final del núcleo, severidad Media):

Varios endpoints de TPV y Control Horario filtraban por `<Modelo>.user_id ==
current_user.id` en vez de por la(s) empresa(s) del usuario (UserCompany). Esto no
es una fuga entre empresas distintas, pero es incorrecto para cualquier empresa con
MAS DE UN USUARIO: un segundo encargado vinculado vía UserCompany no veía el
catálogo de productos, el perfil fiscal, las reservas ni los fichajes de SU PROPIA
empresa, solo lo que él mismo había creado/registrado.

Estos tests fijan el comportamiento correcto:
  * un segundo usuario de la MISMA empresa ve y puede operar sobre los mismos
    productos TPV, perfil fiscal, reservas y fichajes que el primero;
  * un usuario de una empresa DISTINTA sigue sin ver nada de lo anterior
    (aislamiento cross-tenant real, sin fuga).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.erp import FiscalProfile, TPVProduct
from app.models.reservation import Reservation
from app.models.time_tracking import RecordStatus, TimeTrackingRecord
from app.models.user import User

from services import smart_time_control_service as sm
from services.time_cost_engine_v1 import _active_record as tce_active_record


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
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def _mk_user(db: Session, *, tag: str) -> User:
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"e1_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"E1 {tag}",
        is_active=True,
        role="owner",
    )
    db.add(user)
    db.flush()
    return user


def _mk_company(db: Session, *, tag: str) -> Company:
    suf = uuid.uuid4().hex[:8]
    company = Company(company_name=f"E1 Co {tag} {suf}", slug=f"e1-{tag}-{suf}")
    db.add(company)
    db.flush()
    return company


def _link(db: Session, user: User, company: Company, *, role: str = "owner") -> None:
    db.add(UserCompany(user_id=user.id, company_id=company.id, role=role))


def _as(client: TestClient, user: User) -> TestClient:
    app.dependency_overrides[get_current_active_user] = lambda: user
    return client


def _two_users_same_company(db: Session):
    """owner + segundo encargado vinculados a la MISMA empresa vía UserCompany."""
    company = _mk_company(db, tag="shared")
    owner = _mk_user(db, tag="owner")
    second = _mk_user(db, tag="second")
    _link(db, owner, company, role="owner")
    _link(db, second, company, role="owner")
    db.commit()
    db.refresh(owner)
    db.refresh(second)
    db.refresh(company)
    return owner, second, company


def _outsider(db: Session):
    """Usuario de una empresa DISTINTA (no debe ver nada de las fixtures anteriores)."""
    other_company = _mk_company(db, tag="other")
    outsider = _mk_user(db, tag="outsider")
    _link(db, outsider, other_company, role="owner")
    db.commit()
    db.refresh(outsider)
    return outsider


# --------------------------------------------------------------------------- TPVProduct


def test_second_user_can_see_and_edit_company_product(db: Session, client: TestClient):
    owner, second, _company = _two_users_same_company(db)
    outsider = _outsider(db)

    _as(client, owner)
    resp = client.post(
        "/api/v1/tpv/products",
        json={"name": "Café", "price": 1.5, "category": "bebidas", "iva_rate": 10.0},
    )
    assert resp.status_code == 200, resp.text
    product_id = resp.json()["product"]["id"]

    # El segundo usuario de la MISMA empresa ve el producto en el listado (ya funcionaba)
    _as(client, second)
    resp = client.get("/api/v1/tpv/products")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["products"]]
    assert product_id in ids

    # E1: el segundo usuario puede EDITARLO (antes daba 404 "no encontrado o sin permisos")
    resp = client.put(
        f"/api/v1/tpv/products/{product_id}",
        json={"name": "Café con leche", "price": 1.8, "category": "bebidas", "iva_rate": 10.0},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["product"]["name"] == "Café con leche"

    # El panel /tpv (info) y /tpv/status reflejan el total de la EMPRESA, no solo "lo mío"
    resp = client.get("/api/v1/tpv/status")
    assert resp.status_code == 200
    assert resp.json()["products_count"] >= 1

    # El outsider (otra empresa) NO ve el producto
    _as(client, outsider)
    resp = client.get("/api/v1/tpv/products")
    assert resp.status_code == 200
    assert product_id not in [p["id"] for p in resp.json()["products"]]
    resp = client.put(
        f"/api/v1/tpv/products/{product_id}",
        json={"name": "Hackeado", "price": 0.01, "category": "bebidas", "iva_rate": 10.0},
    )
    assert resp.status_code == 404


def test_second_user_can_add_company_product_to_cart(db: Session, client: TestClient):
    owner, second, _company = _two_users_same_company(db)

    _as(client, owner)
    resp = client.post(
        "/api/v1/tpv/products",
        json={"name": "Tarta", "price": 3.0, "category": "postres", "iva_rate": 10.0},
    )
    assert resp.status_code == 200, resp.text
    product_id = resp.json()["product"]["id"]

    # E1: add_to_cart filtraba solo por user_id -> el segundo usuario no podia
    # anadir al carrito un producto creado por el primero.
    _as(client, second)
    resp = client.post("/api/v1/tpv/cart/add", json={"product_id": product_id, "quantity": 2})
    assert resp.status_code == 200, resp.text
    assert resp.json()["cart_item"]["product_id"] == product_id


# --------------------------------------------------------------------------- FiscalProfile


def test_second_user_sees_and_shares_company_fiscal_profile(db: Session, client: TestClient):
    owner, second, _company = _two_users_same_company(db)
    outsider = _outsider(db)

    _as(client, owner)
    resp = client.post(
        "/api/v1/tpv/fiscal-profile",
        json={"vat_regime": "recargo_equivalencia", "apply_recargo_equivalencia": True, "recargo_rate": 5.2},
    )
    assert resp.status_code == 200, resp.text

    # E1: antes devolvia {"profile": None} para el segundo usuario (perfil fiscal
    # "vacio" aunque la empresa ya tuviera uno configurado por el primero).
    _as(client, second)
    resp = client.get("/api/v1/tpv/fiscal-profile")
    assert resp.status_code == 200
    profile = resp.json()["profile"]
    assert profile is not None
    assert profile["vat_regime"] == "recargo_equivalencia"
    assert profile["apply_recargo_equivalencia"] is True

    # El segundo usuario actualiza el perfil: debe REUTILIZAR la misma fila de
    # empresa, no crear una fila nueva.
    resp = client.post(
        "/api/v1/tpv/fiscal-profile",
        json={"vat_regime": "general", "apply_recargo_equivalencia": False, "recargo_rate": None},
    )
    assert resp.status_code == 200, resp.text
    count = db.query(FiscalProfile).filter(FiscalProfile.user_id.in_([owner.id, second.id])).count()
    assert count == 1

    # El owner ve el cambio hecho por el segundo usuario (mismo perfil de empresa)
    _as(client, owner)
    resp = client.get("/api/v1/tpv/fiscal-profile")
    assert resp.json()["profile"]["vat_regime"] == "general"

    # El outsider (otra empresa) sigue sin ver ningun perfil fiscal
    _as(client, outsider)
    resp = client.get("/api/v1/tpv/fiscal-profile")
    assert resp.json()["profile"] is None


# --------------------------------------------------------------------------- Reservation


def test_second_user_sees_and_can_seat_company_reservation(db: Session, client: TestClient):
    owner, second, company = _two_users_same_company(db)
    outsider = _outsider(db)

    today = date.today()
    res = Reservation(
        user_id=owner.id,
        company_id=company.id,
        guest_name="Cliente Prueba",
        guest_phone="600111222",
        reservation_date=today,
        reservation_time="21:00",
        num_guests=2,
        status="pending",
        source="web",
    )
    db.add(res)
    db.commit()
    db.refresh(res)

    # E1: GET /reservations filtraba por user_id -> el segundo usuario no veia
    # la reserva creada bajo la cuenta del primero, aunque fuera la misma empresa.
    _as(client, second)
    resp = client.get("/api/v1/tpv/reservations")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()["reservations"]]
    assert res.id in ids

    resp = client.patch(f"/api/v1/tpv/reservations/{res.id}/seat", json={"table_id": "5", "table_name": "Mesa 5"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["reservation"]["status"] == "seated"

    # El outsider no ve ni puede sentar la reserva de otra empresa
    _as(client, outsider)
    resp = client.get("/api/v1/tpv/reservations")
    assert res.id not in [r["id"] for r in resp.json()["reservations"]]
    resp = client.patch(f"/api/v1/tpv/reservations/{res.id}/seat", json={})
    assert resp.status_code == 404


# --------------------------------------------------------------------------- TimeTrackingRecord


def test_second_user_sees_fichaje_registrado_por_el_primero(db: Session):
    """
    `_today_records_from_db` y `sm.build_employees_smart_status` (control_horario.py +
    smart_time_control_service.py): un fichaje creado bajo el user_id del primer usuario
    debe ser visible para el segundo usuario de la MISMA empresa, y no visible para un
    usuario de otra empresa.
    """
    owner, second, company = _two_users_same_company(db)
    outsider = _outsider(db)

    emp_code = f"EMP-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    rec = TimeTrackingRecord(
        employee_id=emp_code,
        user_id=owner.id,
        company_id=company.id,
        check_in_time=now,
        check_in_method="qr",
        status=RecordStatus.ACTIVE,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    # El propio owner lo ve (comportamiento ya correcto antes del fix)
    today_owner = {r["employee_id"] for r in _today_records(db, owner)}
    assert emp_code in today_owner

    # E1: el segundo usuario debe ver el MISMO fichaje de HOY
    today_second = {r["employee_id"] for r in _today_records(db, second)}
    assert emp_code in today_second

    # Y build_employees_smart_status (usado por /status, /employees, /bootstrap) también
    smart_second, total_active_second = sm.build_employees_smart_status(db, second)
    assert emp_code in smart_second
    assert total_active_second >= 1

    # El outsider (otra empresa) no ve nada de esto
    today_outsider = {r["employee_id"] for r in _today_records(db, outsider)}
    assert emp_code not in today_outsider
    smart_outsider, _total = sm.build_employees_smart_status(db, outsider)
    assert emp_code not in smart_outsider


def test_second_user_sees_detect_patterns_registrado_por_el_primero(db: Session):
    """
    `sm.detect_patterns` (usado por el endpoint de insights de control horario):
    mismo bug E1 que `build_employees_smart_status` -- filtraba por
    TimeTrackingRecord.user_id == user.id, por lo que un segundo usuario de la
    MISMA empresa veia 0 segmentos completados/retrasos aunque el fichaje
    existiera para su empresa (registrado bajo la cuenta del primer usuario).
    """
    owner, second, company = _two_users_same_company(db)
    outsider = _outsider(db)

    emp_code = f"EMP-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    rec = TimeTrackingRecord(
        employee_id=emp_code,
        user_id=owner.id,
        company_id=company.id,
        check_in_time=now - timedelta(hours=8),
        check_out_time=now,
        check_in_method="qr",
        status=RecordStatus.COMPLETED,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    patterns_owner = sm.detect_patterns(db, owner, [emp_code])
    assert patterns_owner["ausencias_proxies"][emp_code]["completed_segments_14d"] >= 1

    # E1: el segundo usuario de la MISMA empresa debe ver el mismo segmento completado
    patterns_second = sm.detect_patterns(db, second, [emp_code])
    assert patterns_second["ausencias_proxies"][emp_code]["completed_segments_14d"] >= 1

    # El outsider (otra empresa) no ve nada
    patterns_outsider = sm.detect_patterns(db, outsider, [emp_code])
    assert patterns_outsider["ausencias_proxies"][emp_code]["completed_segments_14d"] == 0


def _today_records(db: Session, user: User):
    """Reimplementa la query de `_today_records_from_db` sin pasar por el router
    (evita depender del estado global de control_horario_service en el test)."""
    from app.api.v1.endpoints.control_horario import _today_records_from_db

    return _today_records_from_db(db, user)


def test_second_user_can_checkout_record_opened_by_first_user_time_cost_engine_v1(db: Session):
    """
    `_active_record` (services/time_cost_engine_v1.py), usado por `register_checkin`
    (entrada/salida/pausa real del endpoint /api/v1/checkin): antes de E1, si el
    "entrada" lo registraba un usuario y el "salida" lo intentaba OTRO usuario de la
    MISMA empresa, no se encontraba la sesión abierta.
    """
    owner, second, company = _two_users_same_company(db)
    outsider = _outsider(db)

    emp_code = f"EMP-{uuid.uuid4().hex[:8]}"
    rec = TimeTrackingRecord(
        employee_id=emp_code,
        user_id=owner.id,
        company_id=company.id,
        check_in_time=datetime.now(timezone.utc) - timedelta(hours=1),
        check_in_method="qr",
        status=RecordStatus.ACTIVE,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    # El segundo usuario SI encuentra la sesión abierta por el primero (mismo cid)
    found = tce_active_record(db, company_id=company.id, user_id=second.id, employee_id=emp_code)
    assert found is not None
    assert found.id == rec.id

    # El outsider (otra empresa) no la encuentra aunque conozca el employee_id
    not_found = tce_active_record(db, company_id=outsider_company_id(db, outsider), user_id=outsider.id, employee_id=emp_code)
    assert not_found is None


def outsider_company_id(db: Session, outsider: User) -> int:
    link = db.query(UserCompany).filter(UserCompany.user_id == outsider.id).first()
    assert link is not None
    return link.company_id
