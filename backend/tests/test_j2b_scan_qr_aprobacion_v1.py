"""J2b: QR fiscal >= 500 EUR -> aprobacion `register_qr_payment` que SI se completa (borrador de
factura + caja, una sola vez, empresa del servidor) y recuperacion de aprobaciones atascadas
en `executing` (nunca se re-ejecutan)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.cashflow_ledger import CashflowLedgerEntry
from app.models.company import Company, UserCompany
from app.models.customer import Customer
from app.models.erp import Invoice
from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval
from services.zeus_human_approval_v1 import list_pending

SCAN = "/api/v1/scan/qr"
CORE = "/api/v1/zeus-core"


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    try:  # 0061 (J2b defecto 2); ausente en bases anteriores
        from app.db.base import _migrate_zeus_approvals_executing_at

        _migrate_zeus_approvals_executing_at()
    except ImportError:
        pass
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


def _seed(db: Session, tag: str, role: str = "owner", company=None):
    suf = uuid.uuid4().hex[:8]
    if company is None:
        company = Company(company_name=f"J2b {tag} {suf}", slug=f"j2b-{tag}-{suf}")
        db.add(company)
        db.flush()
    user = User(
        email=f"j2b_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"J2b {tag}",
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role=role))
    db.commit()
    db.refresh(user)
    db.refresh(company)
    return user, company


def _as(user):
    app.dependency_overrides[get_current_active_user] = lambda: user


def _qr(client, name, amount, email=None):
    data = f"ZEUS|{name}|{amount}|EUR" + (f"|{email}" if email else "")
    return client.post(SCAN, json={"data": data})


def _effects(db, cid):
    db.expire_all()
    return (
        db.query(Invoice).filter(Invoice.company_id == cid).count(),
        db.query(CashflowLedgerEntry).filter(CashflowLedgerEntry.company_id == cid).count(),
        db.query(Customer).filter(Customer.company_id == cid).count(),
    )


def _resolve(client, aid, approve=True):
    return client.post(f"{CORE}/approvals/{aid}/resolve", json={"approve": approve})


# ---------------------------------------------------------------- defecto 1


def test_qr_ge_500_queda_pendiente_sin_efectos(db, client):
    owner, co = _seed(db, "pend")
    _as(owner)
    r = _qr(client, "Cliente Grande", 800, "grande@example.com")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["needs_approval"] is True and body["executed"] is False
    row = db.get(ZeusPendingApproval, body["approval_id"])
    assert row.status == "pending" and row.action_type == "register_qr_payment"
    assert _effects(db, co.id) == (0, 0, 0)  # ni factura, ni caja, ni cliente


def test_aprobar_ejecuta_borrador_y_caja_una_vez(db, client):
    owner, co = _seed(db, "ok")
    _as(owner)
    aid = _qr(client, "Cliente Grande", 800, "grande@example.com").json()["approval_id"]
    r = _resolve(client, aid)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "executed"
    assert _effects(db, co.id) == (1, 1, 1)
    inv = db.query(Invoice).filter(Invoice.company_id == co.id).one()
    cust = db.query(Customer).filter(Customer.company_id == co.id).one()
    assert float(inv.total) == 800.0 and inv.customer_id == cust.id and cust.name == "Cliente Grande"
    assert str(inv.status).lower().endswith("draft")  # borrador, no emitida
    led = db.query(CashflowLedgerEntry).filter(CashflowLedgerEntry.company_id == co.id).one()
    assert float(led.amount) == 800.0 and led.direction == "in" and led.invoice_id == inv.id
    # segunda aprobacion -> 409, sin duplicar
    assert _resolve(client, aid).status_code == 409
    assert _effects(db, co.id) == (1, 1, 1)
    row = db.get(ZeusPendingApproval, aid)
    assert row.status == "executed"
    acts = {a.action_type for a in db.query(AgentActivity).filter(AgentActivity.company_id == co.id)}
    assert "approval_executed" in acts and "agent_action_register_qr_payment" in acts


def test_cliente_existente_se_reutiliza(db, client):
    owner, co = _seed(db, "reuse")
    _as(owner)
    cid = _qr(client, "Ana", 100, "ana@example.com").json()["customer_id"]  # <500 crea cliente
    assert cid
    aid = _qr(client, "Ana", 900, "ana@example.com").json()["approval_id"]
    assert _resolve(client, aid).status_code == 200
    inv = db.query(Invoice).filter(Invoice.company_id == co.id, Invoice.total == 900).one()
    assert inv.customer_id == cid
    assert db.query(Customer).filter(Customer.company_id == co.id).count() == 1


def test_rechazar_no_deja_efectos(db, client):
    owner, co = _seed(db, "rej")
    _as(owner)
    aid = _qr(client, "Cliente Grande", 800).json()["approval_id"]
    r = _resolve(client, aid, approve=False)
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert _effects(db, co.id) == (0, 0, 0)
    assert _resolve(client, aid).status_code == 409  # no se puede aprobar tras rechazar
    assert _effects(db, co.id) == (0, 0, 0)


def test_otro_usuario_y_otra_empresa(db, client):
    owner, co = _seed(db, "iso")
    mate, _ = _seed(db, "mate", role="company_admin", company=co)
    outsider, _co2 = _seed(db, "out")
    _as(owner)
    aid = _qr(client, "Cliente Grande", 800).json()["approval_id"]
    _as(mate)
    assert _resolve(client, aid).status_code == 403  # solo el solicitante aprueba
    _as(outsider)
    assert _resolve(client, aid).status_code == 404  # empresa ajena: no revela existencia
    assert _resolve(client, aid, approve=False).status_code == 404
    assert _effects(db, co.id) == (0, 0, 0)
    assert db.get(ZeusPendingApproval, aid).status == "pending"


def test_empresa_ajena_en_el_scan_no_crea_nada(db, client):
    owner, co = _seed(db, "scanx")
    outsider, co2 = _seed(db, "scany")
    _as(outsider)
    r = client.post(SCAN, json={"data": "ZEUS|Intruso|900|EUR", "company_id": co.id})
    assert r.status_code == 403, r.text
    assert _effects(db, co.id) == (0, 0, 0)
    assert db.query(ZeusPendingApproval).filter(ZeusPendingApproval.company_id == co.id).count() == 0


def test_qr_lt_500_sin_cambios_de_comportamiento(db, client):
    owner, co = _seed(db, "low")
    _as(owner)
    r = _qr(client, "Cliente Pequeno", 120, "peq@example.com")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["executed"] is True and body["needs_approval"] is False
    assert body["invoice_id"] and body["cashflow_updated"] is True
    assert _effects(db, co.id) == (1, 1, 1)
    assert db.query(ZeusPendingApproval).filter(ZeusPendingApproval.company_id == co.id).count() == 0


def test_payload_malicioso_se_limpia_a_lista_blanca(db, client):
    owner, co = _seed(db, "wl")
    other_user, other_co = _seed(db, "wl2")
    _as(owner)
    r = client.post(
        f"{CORE}/agent/execute",
        json={"agent": "RAFAEL", "action": "register_qr_payment",
              "payload": {"customer_name": "Cliente X", "amount": 700, "company_id": other_co.id, "user_id": other_user.id}},
    )
    assert r.status_code == 200, r.text
    row = db.get(ZeusPendingApproval, r.json()["approval_id"])
    import json as _j

    assert set(_j.loads(row.payload_json)) == {"customer_name", "email", "amount", "currency", "source"}
    assert _resolve(client, row.id).status_code == 200
    assert _effects(db, co.id)[0] == 1 and _effects(db, other_co.id) == (0, 0, 0)


# ---------------------------------------------------------------- defecto 2


def _stuck(db, user, co, minutes_ago, action="generate_invoice", payload='{"invoice_id": 1}'):
    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    row = ZeusPendingApproval(
        company_id=co.id, user_id=user.id, agent_name="RAFAEL", action_type=action,
        payload_json=payload, status="executing", role_required="ceo",
        resolved_at=ts, executing_at=ts,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_recuperacion_pasa_antigua_a_failed_sin_reejecutar(db, monkeypatch):
    from services.zeus_human_approval_v1 import recover_stuck_approvals

    owner, co = _seed(db, "rec")
    calls = []

    async def _boom(*a, **k):
        calls.append(1)
        raise AssertionError("no debe re-ejecutar")

    monkeypatch.setattr("services.zeus_agent_executor_v1.execute_agent_action", _boom)
    # QR real a medias: aprobacion de cobro en executing hace 60 min
    row = _stuck(db, owner, co, 60, action="register_qr_payment",
                 payload='{"customer_name":"X","amount":900,"currency":"EUR","source":"qr_scan"}')
    n = recover_stuck_approvals(db, company_id=co.id)
    assert n == 1 and calls == []
    db.expire_all()
    row = db.get(ZeusPendingApproval, row.id)
    assert row.status == "failed" and "interrumpida" in row.result_json.lower()
    assert "puede haberse producido el efecto" in row.result_json
    assert _effects(db, co.id) == (0, 0, 0)  # nada se re-ejecuto
    act = (
        db.query(AgentActivity)
        .filter(AgentActivity.company_id == co.id, AgentActivity.action_type == "approval_failed")
        .first()
    )
    assert act is not None and act.status == "failed"
    from sqlalchemy import text

    ev = db.execute(
        text("SELECT count(*) FROM thalos_security_events WHERE event_type='approval_execution_interrupted' AND company_id=:c"),
        {"c": co.id},
    ).scalar()
    assert ev == 1
    assert recover_stuck_approvals(db, company_id=co.id) == 0  # idempotente


def test_recuperacion_no_toca_filas_recientes(db):
    from services.zeus_human_approval_v1 import recover_stuck_approvals

    owner, co = _seed(db, "fresh")
    row = _stuck(db, owner, co, 2)
    assert recover_stuck_approvals(db, company_id=co.id) == 0
    db.expire_all()
    assert db.get(ZeusPendingApproval, row.id).status == "executing"


def test_recuperacion_por_empresa_no_toca_otra(db):
    from services.zeus_human_approval_v1 import recover_stuck_approvals

    u1, co1 = _seed(db, "ra")
    u2, co2 = _seed(db, "rb")
    r1, r2 = _stuck(db, u1, co1, 60), _stuck(db, u2, co2, 60)
    assert recover_stuck_approvals(db, company_id=co1.id) == 1
    db.expire_all()
    assert db.get(ZeusPendingApproval, r1.id).status == "failed"
    assert db.get(ZeusPendingApproval, r2.id).status == "executing"


def test_listar_pendientes_recupera_solo_la_empresa_consultada(db):
    u1, co1 = _seed(db, "la")
    u2, co2 = _seed(db, "lb")
    r1, r2 = _stuck(db, u1, co1, 60), _stuck(db, u2, co2, 60)
    list_pending(db, user=u1, company_id=co1.id)
    db.expire_all()
    assert db.get(ZeusPendingApproval, r1.id).status == "failed"
    assert db.get(ZeusPendingApproval, r2.id).status == "executing"


def test_fila_legacy_sin_executing_at_usa_resolved_at(db):
    from services.zeus_human_approval_v1 import recover_stuck_approvals

    owner, co = _seed(db, "leg")
    row = _stuck(db, owner, co, 60)
    row.executing_at = None
    db.commit()
    assert recover_stuck_approvals(db, company_id=co.id) == 1


# ---------------------------------------------------------------- vuelta 1 del revisor

BAD_AMOUNTS = [-5, 0, "nan", "inf", "1e400", 1e12, "abc"]


def _no_state(db, co):
    assert _effects(db, co.id) == (0, 0, 0)
    assert db.query(ZeusPendingApproval).filter(ZeusPendingApproval.company_id == co.id).count() == 0


@pytest.mark.parametrize("amount", BAD_AMOUNTS)
def test_importe_invalido_por_agent_execute_no_abre_aprobacion(db, client, amount):
    owner, co = _seed(db, "badx")
    _as(owner)
    r = client.post(
        f"{CORE}/agent/execute",
        json={"agent": "RAFAEL", "action": "register_qr_payment",
              "payload": {"customer_name": "Cliente Malo", "amount": amount}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["success"] is False and r.json().get("needs_approval") is not True
    _no_state(db, co)


@pytest.mark.parametrize("amount", ["-5", "0", "nan", "inf", "1e400", "1e12", "abc", "-inf"])
def test_importe_invalido_por_scan_qr_422_sin_efectos(db, client, amount):
    owner, co = _seed(db, "bads")
    _as(owner)
    r = _qr(client, "Cliente Malo", amount)
    assert r.status_code == 422, r.text
    _no_state(db, co)


def test_moneda_invalida_por_scan_qr_422(db, client):
    owner, co = _seed(db, "badc")
    _as(owner)
    r = client.post(SCAN, json={"data": "ZEUS|Cliente Malo|900|EUR€!!"})
    assert r.status_code == 422, r.text
    _no_state(db, co)


def test_caja_no_registrada_no_declara_exito(db, client, monkeypatch):
    owner, co = _seed(db, "nocash")
    _as(owner)
    aid = _qr(client, "Cliente Grande", 800, "grande@example.com").json()["approval_id"]
    # la entrada de caja no llega al ledger (guard/integridad): el evento no escribe nada
    monkeypatch.setattr("services.scan_flow_service_v1.emit_cashflow_updated", lambda **k: None)
    r = _resolve(client, aid)
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["status"] == "failed" and body["success"] is False
    assert body["result"]["status"] == "cashflow_not_recorded"
    db.expire_all()
    row = db.get(ZeusPendingApproval, aid)
    assert row.status == "failed" and "cashflow_not_recorded" in row.result_json
    assert db.query(CashflowLedgerEntry).filter(CashflowLedgerEntry.company_id == co.id).count() == 0


def _run_execution_with_recovery(db, owner, co, monkeypatch, result):
    """La ejecucion 'viva' tarda mas que el umbral: durante ella otro proceso recupera la fila."""
    import asyncio

    from services.zeus_human_approval_v1 import (
        execute_approval, recover_stuck_approvals, request_approval, resolve_approval,
    )

    row = request_approval(db, user=owner, company_id=co.id, agent_name="RAFAEL",
                           action_type="generate_invoice", payload={"invoice_id": 1})
    row = resolve_approval(db, approval_id=row.id, user=owner, approve=True)
    seen = {}

    async def _slow(*a, **k):
        seen["recovered"] = recover_stuck_approvals(db, company_id=co.id, older_than_minutes=-1)
        seen["status_during"] = db.get(ZeusPendingApproval, row.id).status
        if isinstance(result, Exception):
            raise result
        return {**result, "company_id": co.id}

    monkeypatch.setattr("services.zeus_agent_executor_v1.execute_agent_action", _slow)
    out = asyncio.run(execute_approval(db, row=row, user=owner))
    return out, seen


def test_carrera_ejecucion_viva_terminada_tras_recuperacion_queda_executed(db, monkeypatch):
    from sqlalchemy import text

    owner, co = _seed(db, "race1")
    out, seen = _run_execution_with_recovery(
        db, owner, co, monkeypatch, {"success": True, "executed": True, "message": "ok"})
    assert seen["recovered"] == 1 and seen["status_during"] == "failed"
    db.expire_all()
    row = db.get(ZeusPendingApproval, out.id)
    assert row.status == "executed" and row.executing_at is not None  # estado final veraz
    assert '"recovered_then_completed": true' in row.result_json and '"interrupted"' not in row.result_json
    acts = {a.action_type for a in db.query(AgentActivity).filter(AgentActivity.company_id == co.id)}
    assert {"approval_late_completion", "approval_executed"} <= acts
    n = db.execute(text("SELECT count(*) FROM thalos_security_events WHERE company_id=:c AND "
                        "event_type IN ('approval_execution_interrupted','approval_completed_after_interruption')"),
                   {"c": co.id}).scalar()
    assert n == 2


def test_carrera_ejecucion_que_falla_tras_recuperacion_queda_failed_con_error_real(db, monkeypatch):
    owner, co = _seed(db, "race2")
    out, seen = _run_execution_with_recovery(db, owner, co, monkeypatch, RuntimeError("boom real"))
    assert seen["recovered"] == 1
    db.expire_all()
    row = db.get(ZeusPendingApproval, out.id)
    assert row.status == "failed" and "boom real" in row.result_json
    assert '"recovered_then_completed": true' in row.result_json
