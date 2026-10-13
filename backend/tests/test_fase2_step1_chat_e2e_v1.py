"""Fase 2 / Step 1 — extremo a extremo por HTTP (auth, guard THALOS por peticion, modulos reales de la
empresa, orquestador, ejecutor, registro): las consultas reales nuevas desde el chat de ZEUS
(/jarvis/message) y desde el chat del PROPIO agente (/chat/{agente}/chat), con `execution` y `status`.
Sin red ni LLM real (run_chat sustituido por un stub que delata si se llamo al modelo)."""

from __future__ import annotations

import uuid
from datetime import timedelta

from app.core.auth import get_current_active_user
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.erp import Invoice, InvoiceStatus
from app.models.fiscal import TPVSale
from services.local_day_v1 import day_bounds_utc, resolve_day

from test_jarvis_acciones_ops_v1 import _env, _user, approvals, client, db, say  # noqa: F401

LLM_STUB = "respuesta-llm-stub"


def agent_say(client, user, agent, message):
    app.dependency_overrides[get_current_active_user] = lambda: user
    r = client.post(f"/api/v1/chat/{agent}/chat", json={"message": message, "thread_id": f"t-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200, r.text
    return r.json()


def _sale(db, user, cid, total):
    start, end = day_bounds_utc(resolve_day("yesterday"))
    db.add(TPVSale(user_id=user.id, company_id=cid, ticket_id=f"T-{uuid.uuid4().hex[:10]}",
                   document_type="ticket", sale_date=start + (end - start) / 2, payment_method="efectivo",
                   subtotal=total, tax_amount=0, total=total))
    db.commit()


def test_cierre_de_ayer_por_jarvis_real_y_aislado_por_empresa(db, client):
    ua, ca = _user(db)  # bar_restaurant: modulo tpv activo (configuracion real)
    ub, cb = _user(db)
    _sale(db, ua, ca.id, 30.0)
    _sale(db, ub, cb.id, 75.0)
    oa, ob = say(client, ua, "¿cómo fue el cierre de ayer?"), say(client, ub, "cierre de ayer")
    assert oa["success"] and oa["executed_action"] and oa["execution"]["intent"] == "get_daily_close"
    assert oa["execution"]["metrics"]["total"] == 30.0 and ob["execution"]["metrics"]["total"] == 75.0
    assert "30,00 €" in oa["message"] and "75" not in oa["message"]
    assert oa.get("status") is None
    assert not approvals(db, ua)
    db.expire_all()
    assert db.query(AgentActivity).filter(AgentActivity.company_id == ca.id,
                                          AgentActivity.action_type == "agent_action_get_daily_close").count() == 1


def test_bloqueo_por_modulo_llega_con_status(db, client):
    u, _ = _user(db, company_type="office")  # oficina: sin TPV
    out = say(client, u, "cierre de ayer")
    assert out["success"] is False and out["status"] == "blocked_module" and "TPV" in out["message"]


def test_pedidos_bloqueo_honesto_con_status(db, client):
    u, _ = _user(db)
    out = say(client, u, "¿qué pedidos tengo esta semana?")
    assert out["success"] is False and out["status"] == "not_available"
    assert "no tiene un registro de pedidos" in out["message"]
    assert out["execution"]["status"] == "not_available"


def test_consulta_real_desde_el_workspace_del_propio_agente(db, client):
    u, c = _user(db)
    db.add(Invoice(invoice_number=f"F-{uuid.uuid4().hex[:8]}", company_id=c.id, status=InvoiceStatus.SENT,
                   total=120.0, amount_paid=0.0))
    db.commit()
    out = agent_say(client, u, "rafael", "facturas pendientes")
    assert out["message"] != LLM_STUB
    assert out["success"] and out["executed_action"] and out["intent"] == "get_pending_invoices"
    assert out["execution"]["metrics"]["pending_count"] == 1 and "120,00 €" in out["message"]


def test_workspace_de_agente_otra_cosa_sigue_al_modelo(db, client):
    u, _ = _user(db)
    # conversacion normal -> LLM
    assert agent_say(client, u, "rafael", "explícame qué es el IVA")["message"] == LLM_STUB
    # consulta de OTRO agente pedida en el workspace de PERSEO -> no se ejecuta ahi (va al modelo)
    out = agent_say(client, u, "perseo", "facturas pendientes")
    assert out["message"].startswith(LLM_STUB) and not out.get("executed_action")
    # negacion -> modelo, nada ejecutado
    assert agent_say(client, u, "rafael", "no me digas las facturas pendientes")["message"] == LLM_STUB


def test_workspace_de_agente_bloqueo_por_modulo_con_status(db, client):
    u, _ = _user(db, company_type="office")  # oficina: sin control horario
    out = agent_say(client, u, "afrodita", "¿quién ha fichado hoy?")
    assert out["success"] is False and out["status"] == "blocked_module" and out["message"] != LLM_STUB


def test_workspace_de_agente_aislado_por_empresa(db, client):
    ua, ca = _user(db)
    ub, cb = _user(db)
    db.add(Invoice(invoice_number=f"F-{uuid.uuid4().hex[:8]}", company_id=cb.id, status=InvoiceStatus.OVERDUE,
                   total=999.0, amount_paid=0.0))
    db.commit()
    out = agent_say(client, ua, "rafael", "facturas pendientes")
    assert out["execution"]["metrics"]["pending_count"] == 0
    assert out["message"] == "No tienes facturas pendientes de cobro."
