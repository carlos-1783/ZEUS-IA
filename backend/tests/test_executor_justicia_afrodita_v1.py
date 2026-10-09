"""J9c: acciones reales de JUSTICIA y AFRODITA en el ejecutor de agentes + control de modulos en
_dispatch para todas las acciones. Sin red ni LLM."""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.erp import InventoryMovement, Product
from app.models.legal_document import LegalDocument
from app.models.ops_route import OpsRoute
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval
from services import module_gate
from services.zeus_agent_executor_v1 import execute_agent_action

BASE = "/api/v1/zeus-core"


@pytest.fixture()
def db():
    from app.db.base import _migrate_zeus_approvals_chat_columns, _migrate_zeus_approvals_execution_columns

    Base.metadata.create_all(bind=engine)
    _migrate_zeus_approvals_execution_columns()
    _migrate_zeus_approvals_chat_columns()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client():
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def writes_on(monkeypatch):
    monkeypatch.setattr("services.afrodita_unified_control.writes_enabled", lambda: True)


def _user(db, company_type="bar_restaurant", role="owner", company=None):
    suf = uuid.uuid4().hex[:8]
    if company is None:
        company = Company(company_name=f"J9c {suf}", slug=f"j9c-{suf}", company_type=company_type)
        db.add(company)
        db.flush()
    u = User(email=f"j9c_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J9c", is_active=True)
    db.add(u)
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=company.id, role=role))
    db.commit()
    db.refresh(u)
    db.refresh(company)
    return u, company


def _product(db, company, stock=10.0, threshold=2.0, name="Cafe"):
    suf = uuid.uuid4().hex[:8]
    p = Product(sku=f"J9C-{suf}", name=f"{name} {suf}", price=1.5, company_id=company.id,
                track_inventory=True, quantity_on_hand=stock, low_stock_threshold=threshold)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _run(db, user, agent, action, payload=None):
    return asyncio.run(execute_agent_action(db, user=user, agent=agent, action=action, payload=payload or {}))


def _as(user):
    app.dependency_overrides[get_current_active_user] = lambda: user


def _activities(db, company_id, action, status=None):
    db.expire_all()
    rows = db.query(AgentActivity).filter(AgentActivity.company_id == company_id).all()
    out = []
    for r in rows:
        d = r.details if isinstance(r.details, dict) else json.loads(r.details or "{}")
        if d.get("action") == action and (status is None or r.status == status):
            out.append((r, d))
    return out


# ------------------------------------------------------------------ JUSTICIA (lectura)
def test_justicia_estado_legal_solo_de_su_usuario(db):
    ua, ca = _user(db)
    ub, cb = _user(db)
    for u, c, n in ((ua, ca, 2), (ub, cb, 5)):
        for i in range(n):
            db.add(LegalDocument(user_id=u.id, company_id=c.id, doc_type="contrato", content="x", status="draft"))
    db.commit()
    ra = _run(db, ua, "JUSTICIA", "get_legal_status")
    rb = _run(db, ub, "JUSTICIA", "get_legal_status")
    assert ra["success"] and ra["executed"] and ra["data"]["legal_documents"] == 2
    assert rb["data"]["legal_documents"] == 5
    assert ra["company_id"] == ca.id and rb["company_id"] == cb.id
    assert _activities(db, ca.id, "get_legal_status", "completed")


def test_justicia_auditoria_real_y_error_real_si_desactivada(db, monkeypatch):
    u, c = _user(db)
    db.add(LegalDocument(user_id=u.id, company_id=c.id, doc_type="nda", content="x", status="draft"))
    db.commit()
    r = _run(db, u, "JUSTICIA", "run_compliance_audit")
    assert r["success"] and r["executed"] is True
    assert r["data"]["real_execution"] is True and r["data"]["legal_documents_count"] == 1
    from app.core.config import settings

    monkeypatch.setattr(settings, "JUSTICE_REAL_AUDIT_ENABLED", False)
    r2 = _run(db, u, "JUSTICIA", "run_compliance_audit")
    assert r2["success"] is False and r2["executed"] is False and "JUSTICE_REAL_AUDIT_ENABLED" in r2["message"]
    assert _activities(db, c.id, "run_compliance_audit", "failed")


def test_accion_de_otro_agente_se_rechaza(db):
    u, c = _user(db)
    r = _run(db, u, "RAFAEL", "get_legal_status")
    assert r["success"] is False and r["status"] == "agent_mismatch"
    r = _run(db, u, "JUSTICIA", "get_inventory_status")
    assert r["status"] == "agent_mismatch"


# ------------------------------------------------------------------ AFRODITA (lectura)
def test_afrodita_inventario_solo_de_su_empresa(db):
    ua, ca = _user(db)
    ub, cb = _user(db)
    pa = _product(db, ca, stock=1.0, threshold=2.0)
    _product(db, ca, stock=50.0)
    pb = _product(db, cb, stock=7.0)
    ra = _run(db, ua, "AFRODITA", "get_inventory_status")
    rb = _run(db, ub, "AFRODITA", "get_inventory_status")
    assert ra["success"] and ra["executed"] and ra["company_id"] == ca.id
    skus_a = {i["sku"] for i in ra["data"]["items"]}
    assert pa.sku in skus_a and pb.sku not in skus_a and ra["data"]["total_skus"] == 2
    assert ra["data"]["low_stock_count"] == 1 and ra["data"]["low_stock_items"][0]["sku"] == pa.sku
    assert {i["sku"] for i in rb["data"]["items"]} == {pb.sku}


def test_afrodita_estado_turno_lee_bd_y_exige_control_horario(db):
    ub, cb = _user(db, "bar_restaurant")
    r = _run(db, ub, "AFRODITA", "get_shift_status")
    assert r["success"] and r["executed"] and r["metrics"]["active"] is False
    uo, co = _user(db, "office")
    r2 = _run(db, uo, "AFRODITA", "get_shift_status")
    assert r2["success"] is False and r2["status"] == "blocked_module" and r2["module"] == "control_horario"


# ------------------------------------------------------------------ AFRODITA (escritura: aprobacion)
def test_ruta_pide_aprobacion_no_ejecuta_y_confirmar_la_crea(db, client, writes_on):
    u, c = _user(db)
    r = _run(db, u, "AFRODITA", "create_ops_route",
             {"origin": "Almacen", "destination": "Local 2", "deliveries": [{"address": "Calle 1"}],
              "company_id": 999999, "user_id": 1})
    assert r["success"] and r["executed"] is False and r["needs_approval"] is True
    assert "Vista previa" in r["message"] and "Almacen" in r["preview"]
    db.expire_all()
    assert db.query(OpsRoute).filter(OpsRoute.company_id == c.id).count() == 0
    row = db.query(ZeusPendingApproval).filter(ZeusPendingApproval.id == r["approval_id"]).one()
    stored = json.loads(row.payload_json)
    assert row.company_id == c.id and row.status == "pending" and row.role_required == "member"
    assert "company_id" not in stored and "user_id" not in stored

    _as(u)
    res = client.post(f"{BASE}/approvals/{row.id}/resolve", json={"approve": True})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "executed"
    db.expire_all()
    routes = db.query(OpsRoute).filter(OpsRoute.company_id == c.id).all()
    assert len(routes) == 1 and routes[0].user_id == u.id and routes[0].origin == "Almacen"
    ev = (db.query(ThalosSecurityEvent)
          .filter(ThalosSecurityEvent.user_id == u.id, ThalosSecurityEvent.event_type == "post_action_audit")
          .order_by(ThalosSecurityEvent.id.desc()).first())
    assert ev.action_taken == "audit_pass"
    assert _activities(db, c.id, "create_ops_route", "completed")


def test_movimiento_confirmar_ejecuta_stock_y_auditoria(db, client, writes_on):
    u, c = _user(db, role="owner")
    p = _product(db, c, stock=10.0)
    r = _run(db, u, "AFRODITA", "create_inventory_movement",
             {"product_id": p.id, "movement_type": "adjustment", "quantity": -3})
    assert r["needs_approval"] is True and "10 -> 7" in r["preview"]
    db.expire_all()
    assert db.query(Product).get(p.id).quantity_on_hand == 10.0
    assert db.query(InventoryMovement).filter(InventoryMovement.product_id == p.id).count() == 0
    row = db.query(ZeusPendingApproval).filter(ZeusPendingApproval.id == r["approval_id"]).one()
    assert row.role_required == "ceo"

    _as(u)
    res = client.post(f"{BASE}/approvals/{row.id}/resolve", json={"approve": True})
    assert res.status_code == 200 and res.json()["status"] == "executed"
    db.expire_all()
    assert db.query(Product).get(p.id).quantity_on_hand == 7.0
    assert db.query(InventoryMovement).filter(InventoryMovement.product_id == p.id).count() == 1
    ev = (db.query(ThalosSecurityEvent)
          .filter(ThalosSecurityEvent.user_id == u.id, ThalosSecurityEvent.event_type == "post_action_audit")
          .order_by(ThalosSecurityEvent.id.desc()).first())
    assert ev.action_taken == "audit_pass" and ev.company_id == c.id


def test_otro_usuario_u_otra_empresa_no_confirma_ni_ve(db, client, writes_on):
    u, c = _user(db)
    other_same, _ = _user(db, company=c, role="owner")
    stranger, _ = _user(db)
    p = _product(db, c, stock=5.0)
    r = _run(db, u, "AFRODITA", "create_inventory_movement", {"product_id": p.id, "quantity": 1})
    aid = r["approval_id"]
    _as(other_same)
    assert client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True}).status_code == 403
    _as(stranger)
    assert client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True}).status_code == 404
    db.expire_all()
    assert db.query(Product).get(p.id).quantity_on_hand == 5.0
    assert db.query(ZeusPendingApproval).get(aid).status == "pending"


def test_movimiento_producto_de_otra_empresa_rechazado(db, writes_on):
    ua, ca = _user(db)
    ub, cb = _user(db)
    pb = _product(db, cb, stock=5.0)
    r = _run(db, ua, "AFRODITA", "create_inventory_movement", {"product_id": pb.id, "quantity": 1})
    assert r["success"] is False and r["status"] == "invalid_payload" and "no encontrado" in r["message"]
    db.expire_all()
    assert db.query(ZeusPendingApproval).filter(ZeusPendingApproval.company_id == ca.id).count() == 0
    # defensa en profundidad del servicio: aunque llegara una aprobacion manipulada, no toca otra empresa
    from fastapi import HTTPException

    from services.afrodita_ops_service_v1 import create_inventory_movement

    with pytest.raises(HTTPException) as e:
        create_inventory_movement(db, ua, product_id=pb.id, movement_type="adjustment", quantity=1, company_id=ca.id)
    assert e.value.status_code == 404
    db.rollback()
    assert db.query(Product).get(pb.id).quantity_on_hand == 5.0


def test_rol_insuficiente_para_movimiento_403_pero_ruta_permitida(db, writes_on):
    from fastapi import HTTPException

    u, c = _user(db, role="member")
    p = _product(db, c)
    with pytest.raises(HTTPException) as e:
        _run(db, u, "AFRODITA", "create_inventory_movement", {"product_id": p.id, "quantity": 1})
    assert e.value.status_code == 403
    db.expire_all()
    assert db.query(ZeusPendingApproval).filter(ZeusPendingApproval.company_id == c.id).count() == 0
    r = _run(db, u, "AFRODITA", "create_ops_route", {"origin": "A", "destination": "B"})
    assert r["needs_approval"] is True


def test_escritura_afrodita_con_flags_desactivadas_error_real(db, monkeypatch):
    monkeypatch.setattr("services.afrodita_unified_control.writes_enabled", lambda: False)
    u, c = _user(db)
    r = _run(db, u, "AFRODITA", "create_ops_route", {"origin": "A", "destination": "B"})
    assert r["success"] is False and r["status"] == "writes_disabled"
    db.expire_all()
    assert db.query(ZeusPendingApproval).filter(ZeusPendingApproval.company_id == c.id).count() == 0


def test_payload_invalido_no_crea_aprobacion(db, writes_on):
    u, c = _user(db)
    for act, pl in (
        ("create_ops_route", {"origin": "", "destination": "B"}),
        ("create_ops_route", {"origin": "A", "destination": "B", "deliveries": "x"}),
        ("create_inventory_movement", {"product_id": "abc", "quantity": 1}),
        ("create_inventory_movement", {"product_id": 1, "quantity": 0}),
    ):
        r = _run(db, u, "AFRODITA", act, pl)
        assert r["success"] is False and r["status"] == "invalid_payload", (act, pl, r)
    assert db.query(ZeusPendingApproval).filter(ZeusPendingApproval.company_id == c.id).count() == 0


# ------------------------------------------------------------------ modulos en _dispatch
def test_modulo_desactivado_bloquea_en_dispatch_con_registro_j7(db, monkeypatch):
    """Acciones del ejecutor con modulo mapeado: se bloquean en _dispatch (camino de ejecucion tras
    aprobacion incluido) sin ejecutar, con status blocked_module y paso ACTUAR en agent_activities."""
    from app.schemas.zeus_action import ZeusAction
    from services.zeus_agent_executor_v1 import _dispatch

    u, c = _user(db, "office")  # office: sin control_horario
    za = ZeusAction(action_type="shift_status", company_id=c.id, user_id=u.id, payload={})
    r = asyncio.run(_dispatch(db, u, "AFRODITA", "get_shift_status", za, {}, force_execute=False))
    assert r["success"] is False and r["executed"] is False and r["status"] == "blocked_module"
    assert r["module"] == "control_horario" and "Control horario" in r["message"]
    rows = _activities(db, c.id, "get_shift_status", "blocked_module")
    assert rows and rows[0][1]["chain_step"] == "ACTUAR" and rows[0][1]["module"] == "control_horario"

    # bar: sin crm -> track_leads bloqueada; office: crm activo -> permitida
    ub, cb = _user(db, "bar_restaurant")
    rb = _run(db, ub, "PERSEO", "track_leads")
    assert rb["status"] == "blocked_module" and rb["module"] == "crm"
    assert _run(db, u, "PERSEO", "track_leads")["success"] is True

    # JUSTICIA exige "agents": si la empresa lo desactivara, no se ejecuta ni se pide nada
    monkeypatch.setattr(module_gate, "active_modules", lambda db_, user_: {"agents": False})
    rj = _run(db, u, "JUSTICIA", "get_legal_status")
    assert rj["status"] == "blocked_module" and rj["module"] == "agents"


def test_acciones_sin_mapeo_siguen_permitidas_y_documentadas(db, monkeypatch):
    """list_customers/cashflow/metrics (y el resto) no tienen modulo claro: permitidas aunque no haya
    ningun modulo activo; el mapa las declara explicitamente."""
    for a in ("get_customers", "get_cashflow", "get_metrics", "create_customer", "send_campaign",
              "generate_invoice", "get_inventory_status", "create_ops_route", "create_inventory_movement"):
        assert a in module_gate.EXECUTOR_UNMAPPED_ACTIONS and a not in module_gate.EXECUTOR_ACTION_MODULE
    monkeypatch.setattr(module_gate, "active_modules", lambda db_, user_: {})
    u, c = _user(db)
    for a in ("get_cashflow", "get_metrics", "get_customers"):
        r = _run(db, u, "ZEUS", a)
        assert r.get("status") != "blocked_module", (a, r)
        assert r["success"] is True
    assert module_gate.check_executor_action(db, u, "get_cashflow") is None


def test_todas_las_acciones_del_ejecutor_estan_clasificadas():
    from services.zeus_agent_executor_v1 import MANDATORY_ACTIONS

    todas = {a for acts in MANDATORY_ACTIONS.values() for a in acts}
    clasificadas = set(module_gate.EXECUTOR_ACTION_MODULE) | set(module_gate.EXECUTOR_UNMAPPED_ACTIONS)
    assert todas <= clasificadas, todas - clasificadas
