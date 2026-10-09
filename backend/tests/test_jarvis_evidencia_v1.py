"""J10: RESPONDER con evidencia (`evidence`) y CONTINUAR (`next_step`). Sin red ni LLM real.

Los agentes son los reales con `chat_completion` sustituido (mismo montaje que J9b). Cubre: borradores de
plan persistidos como DocumentApproval draft del agente, respuesta de agente no-ZEUS, aprobacion pendiente,
recurso creado tras confirmar, acceso directo a la URL de evidencia de otra empresa, mensaje breve,
next_step nulo y registro J7 de CONTINUAR."""

from __future__ import annotations

import uuid

import pytest

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company
from app.models.document_approval import DocumentApproval
from app.models.erp import InventoryMovement
from app.models.ops_route import OpsRoute
from app.models.user import User
from services import jarvis_evidence as jev
from services import jarvis_model_comprehension as mc

# fixtures y ayudantes de J9b / J9e (se importan por nombre para que pytest los use como fixtures)
from test_jarvis_plan_v1 import (  # noqa: F401
    CUST_ACT, MSG_IVA_CORREO, OFFER, OFFER_ACT, FakeClf, _long, _user, approvals, classifier, db, rows, say,
    stack, step, use_model,
)
from test_jarvis_acciones_ops_v1 import _product, writes_on  # noqa: F401

EV = "/api/v1/jarvis/evidence"


def get_ev(stack, user, kind, item_id):
    app.dependency_overrides[get_current_active_user] = lambda: user
    return stack.c.get(f"{EV}/{kind}/{item_id}")


def kinds(out):
    return [e["kind"] for e in out.get("evidence") or []]


def of_kind(out, kind):
    return [e for e in out.get("evidence") or [] if e["kind"] == kind]


def _draft_plan(stack, db):
    u, co = _user(db)
    stack.llm.content["RAFAEL"] = _long("FINAL_BORRADOR")
    use_model(stack, classifier(
        step("AFRODITA", "consulta", "Resumir los turnos"),
        step("RAFAEL", "borrador", "Redactar el correo al gestor", deps=[1])))
    return u, co, say(stack, u, MSG_IVA_CORREO)


# ----------------------------------------------------------------------------- plan con borrador
def test_plan_con_borrador_persiste_draft_del_agente_y_enlaza_sin_incrustar(db, stack):
    u, co, out = _draft_plan(stack, db)
    docs = of_kind(out, "document")
    assert len(docs) == 1 and docs[0]["agent"] == "RAFAEL" and docs[0]["status"] == "draft"
    row = db.query(DocumentApproval).filter(DocumentApproval.id == docs[0]["id"]).one()
    assert row.company_id == co.id and row.user_id == u.id and row.agent_name == "RAFAEL"
    assert row.status == "draft" and "FINAL_BORRADOR" in str(row.document_payload)
    assert docs[0]["url"] == f"{EV}/document/{row.id}"
    # el texto largo NO va ni en message ni en steps[].text: se enlaza
    assert "FINAL_BORRADOR" not in out["message"] and "Ver en el workspace de RAFAEL" in out["message"]
    st = out["steps"][1]
    assert st["text"] == "" and st["evidence"]["id"] == row.id
    assert len(out["message"]) < 600
    # el enlace funciona y entrega el recurso real
    r = get_ev(stack, u, "document", row.id)
    assert r.status_code == 200 and "FINAL_BORRADOR" in str(r.json()["detail"]["payload"])


def test_plan_con_borrador_next_step_y_continuar_j7_con_el_tipo(db, stack):
    u, co, out = _draft_plan(stack, db)
    assert out["next_step"] == "Revisa el borrador en el workspace de RAFAEL y apruébalo."
    assert "next_step_type" not in out  # el tipo es solo de servidor
    cont = [r for r in rows(db, co.id, step="CONTINUAR") if r.details.get("correlation_id") == out["request_id"]]
    assert len(cont) == 1 and cont[0].details["next_step_type"] == "review_draft"
    assert cont[0].details["evidence_kinds"] == ["document"]
    # el registro no copia ni el texto del usuario ni el del borrador/next_step
    blob = str(cont[0].details) + str(cont[0].action_description)
    assert "IVA" not in blob and "FINAL_BORRADOR" not in blob and "Revisa el borrador" not in blob


def test_fallo_al_guardar_el_borrador_conserva_el_texto_y_avisa(db, stack, monkeypatch):
    import services.workspace_deliverables as wd

    def boom(*a, **k):
        raise RuntimeError("bd caida")

    monkeypatch.setattr(wd, "persist_agent_chat_deliverable", boom)
    u, co, out = _draft_plan(stack, db)
    st = out["steps"][1]
    assert st["evidence"] is None and st["text"].endswith("FINAL_BORRADOR")  # nada se pierde
    assert "no se pudo guardar en el workspace" in out["message"]
    assert any("borrador" in w for w in out["warnings"])
    assert out["next_step"] is None and "document" not in kinds(out)


# ----------------------------------------------------------------------------- agente no-ZEUS
def _chat_agent(stack, user, agent, message="hola"):
    app.dependency_overrides[get_current_active_user] = lambda: user
    r = stack.c.post(f"/api/v1/chat/{agent}/chat", json={"message": message, "thread_id": "t-ev"})
    assert r.status_code == 200, r.text
    return r.json()


def test_respuesta_corta_de_agente_no_zeus_enlaza_documento_y_no_toca_el_mensaje(db, stack):
    u, co = _user(db)
    stack.llm.content["RAFAEL"] = "El IVA de este trimestre son 120 euros."
    out = _chat_agent(stack, u, "rafael", "cuanto iva pago")
    assert out["message"] == "El IVA de este trimestre son 120 euros."
    d = of_kind(out, "document")
    assert len(d) == 1 and d[0]["id"] == out["workspace_document_id"] and d[0]["agent"] == "RAFAEL"
    assert db.query(DocumentApproval).filter(DocumentApproval.id == d[0]["id"]).one().company_id == co.id
    assert out["next_step"] is None  # consulta corta: nada logico que proponer


def test_respuesta_larga_de_agente_es_entregable_breve_en_el_chat(db, stack):
    u, co = _user(db)
    stack.llm.content["JUSTICIA"] = _long("FINAL_CONTRATO")
    out = _chat_agent(stack, u, "justicia", "redacta un contrato de confidencialidad")
    assert "FINAL_CONTRATO" not in out["message"] and out["message"].endswith("Ver en el workspace de JUSTICIA.")
    assert len(out["message"]) < 400
    d = of_kind(out, "document")[0]
    assert out["next_step"] == "Revisa el borrador en el workspace de JUSTICIA y apruébalo."
    r = get_ev(stack, u, "document", d["id"])
    assert r.status_code == 200 and "FINAL_CONTRATO" in str(r.json()["detail"]["payload"])  # completo en el workspace
    # el historial persistido del chat lleva lo que vio el usuario (breve)
    from app.models.chat_message import ChatMessage

    last = (db.query(ChatMessage).filter(ChatMessage.user_id == u.id, ChatMessage.role == "assistant")
            .order_by(ChatMessage.id.desc()).first())
    assert last is not None and "FINAL_CONTRATO" not in last.message


# ----------------------------------------------------------------------------- aprobacion y recurso creado
def test_aprobacion_pendiente_evidence_approval_y_next_step_confirmar(db, stack):
    u, co = _user(db)
    use_model(stack, classifier(
        step("JUSTICIA", "consulta", "Revisar el contrato con el proveedor"),
        step("PERSEO", "accion_con_consecuencias", "Enviar la oferta", action_type="send_campaign"),
        actions=[OFFER_ACT]))
    out = say(stack, u, OFFER)
    ap = of_kind(out, "approval")
    assert len(ap) == 1 and ap[0]["id"] == out["approval_id"] and ap[0]["status"] == "pending"
    assert ap[0]["url"] == f"{EV}/approval/{out['approval_id']}" and ap[0]["agent"] == "ZEUS CORE"
    assert out["next_step"] == "Responde «confirmar» para enviarla o «cancelar» para descartarla."
    cont = [r for r in rows(db, co.id, step="CONTINUAR") if r.details.get("correlation_id") == out["request_id"]]
    assert cont and cont[0].details["next_step_type"] == "confirm_pending"
    r = get_ev(stack, u, "approval", out["approval_id"])
    assert r.status_code == 200 and r.json()["detail"]["action_type"] == "send_campaign"
    # cancelar: la evidencia queda como rechazada y no hay nada que proponer
    out2 = say(stack, u, "cancelar")
    assert out2["next_step"] is None and of_kind(out2, "approval")[0]["status"] == "rejected"


def test_crear_cliente_confirmado_enlaza_el_recurso_y_propone_la_oferta(db, stack):
    u, co = _user(db)
    out = say(stack, u, "crea el cliente Ana López con email ana@empresa.es", thread="t-cli")
    assert out["needs_confirmation"] and out["next_step"].startswith("Responde «confirmar» para crear el cliente")
    done = say(stack, u, "confirmar", thread="t-cli")
    assert done["executed_action"] is True
    cu = of_kind(done, "customer")
    assert len(cu) == 1 and cu[0]["agent"] == "ZEUS CORE"
    assert of_kind(done, "approval")[0]["status"] == "executed"
    assert done["next_step"].startswith("¿Quieres enviarle la oferta activa?")
    r = get_ev(stack, u, "customer", cu[0]["id"])
    assert r.status_code == 200 and r.json()["detail"]["email"] == "ana@empresa.es"
    cont = [x for x in rows(db, co.id, step="CONTINUAR") if x.details.get("correlation_id") == done["request_id"]]
    assert cont and cont[0].details["next_step_type"] == "offer_after_customer"


def test_ruta_y_movimiento_confirmados_enlazan_recurso_creado(db, stack, writes_on, monkeypatch):
    u, co = _user(db, company_type="bar_restaurant")
    out = say(stack, u, "crea una ruta de Madrid a Valencia", thread="t-ruta")
    assert out["needs_confirmation"] is True and of_kind(out, "approval")[0]["agent"] == "AFRODITA"
    assert "para crear la ruta" in out["next_step"]
    done = say(stack, u, "confirmar", thread="t-ruta")
    ro = of_kind(done, "route")
    assert len(ro) == 1 and ro[0]["agent"] == "AFRODITA"
    assert db.query(OpsRoute).filter(OpsRoute.id == ro[0]["id"], OpsRoute.company_id == co.id).count() == 1
    assert get_ev(stack, u, "route", ro[0]["id"]).json()["detail"]["destination"] == "Valencia"

    p = _product(db, co, name="Harina de trigo", stock=10)
    say(stack, u, "por favor, registra una entrada de 5 unidades de Harina de trigo", thread="t-mov")
    done = say(stack, u, "confirmar", thread="t-mov")
    mv = of_kind(done, "movement")
    assert len(mv) == 1 and done["next_step"].startswith("Si quieres, consulto el estado del inventario")
    db.expire_all()
    assert db.query(InventoryMovement).filter(InventoryMovement.id == mv[0]["id"],
                                              InventoryMovement.product_id == p.id).count() == 1
    assert get_ev(stack, u, "movement", mv[0]["id"]).json()["detail"]["quantity"] == 5


# ----------------------------------------------------------------------------- registro J7
def test_evidencia_de_registro_j7_con_request_id_solo_pasos_sin_contenido(db, stack):
    u, co = _user(db)
    out = say(stack, u, "crea el cliente Ana López con email ana@empresa.es", thread="t-aud")
    au = of_kind(out, "audit")
    assert len(au) == 1 and au[0]["id"] == out["request_id"] and au[0]["url"] == f"{EV}/audit/{out['request_id']}"
    r = get_ev(stack, u, "audit", out["request_id"])
    assert r.status_code == 200
    steps = r.json()["detail"]["steps"]
    assert {"ESCUCHAR", "RESPONDER"} <= {s["step"] for s in steps}
    assert "ana@empresa.es" not in r.text and "Ana López" not in r.text


# ----------------------------------------------------------------------------- aislamiento por empresa
def test_url_de_evidencia_de_otra_empresa_404_en_todos_los_tipos(db, stack, writes_on):
    a, ca = _user(db)
    b, cb = _user(db)
    # documento + aprobacion pendiente + request_id de A
    stack.llm.content["RAFAEL"] = _long("SECRETO_A")
    use_model(stack, classifier(step("RAFAEL", "borrador", "Redactar un correo al gestor"),
                                step("AFRODITA", "consulta", "Resumir los turnos")))
    out_doc = say(stack, a, MSG_IVA_CORREO, thread="t-a1")
    doc_id = of_kind(out_doc, "document")[0]["id"]
    stack.mp.setattr(mc, "get_client", lambda: None)
    pend = say(stack, a, "crea una ruta de Madrid a Valencia", thread="t-a2")
    done = say(stack, a, "confirmar", thread="t-a2")
    route_id = of_kind(done, "route")[0]["id"]
    cust = say(stack, a, "crea el cliente Ana López con email ana@empresa.es", thread="t-a3")
    cust_done = say(stack, a, "confirmar", thread="t-a3")
    cust_id = of_kind(cust_done, "customer")[0]["id"]
    p = _product(db, ca, name="Harina de trigo", stock=10)
    say(stack, a, "registra una entrada de 5 unidades de Harina de trigo", thread="t-a4")
    mv_id = of_kind(say(stack, a, "confirmar", thread="t-a4"), "movement")[0]["id"]
    targets = [("document", doc_id), ("approval", pend["approval_id"]), ("route", route_id),
               ("customer", cust_id), ("movement", mv_id), ("audit", out_doc["request_id"])]
    for kind, rid in targets:
        assert get_ev(stack, a, kind, rid).status_code == 200, (kind, rid)   # el dueno si
        r = get_ev(stack, b, kind, rid)                                       # otra empresa: nunca
        assert r.status_code == 404, (kind, rid, r.text)
        assert "SECRETO_A" not in r.text and "ana@empresa.es" not in r.text
    # lo mismo con el lado inverso: la evidencia de B no contiene nada de A
    out_b = say(stack, b, "crea una ruta de Madrid a Valencia", thread="t-b1")
    assert {e["id"] for e in out_b["evidence"] if e["kind"] == "approval"} == {out_b["approval_id"]}
    assert approvals(db, b)[0].company_id == cb.id


def test_acceso_sin_sesion_sin_empresa_y_tipo_desconocido(db, stack):
    a, _ = _user(db)
    app.dependency_overrides.clear()
    assert stack.c.get(f"{EV}/document/1").status_code in (401, 403)  # sin credenciales
    suf = uuid.uuid4().hex[:8]
    loner = User(email=f"j10_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
                 full_name="J10", is_active=True)
    db.add(loner)
    db.commit()
    db.refresh(loner)
    assert get_ev(stack, loner, "document", 1).status_code == 403  # sin empresa
    assert get_ev(stack, a, "fichero", 1).status_code == 404       # tipo fuera de contrato
    assert get_ev(stack, a, "document", "abc").status_code == 404
    assert get_ev(stack, a, "audit", "no-es-un-id").status_code == 404


def test_un_id_de_otra_empresa_nunca_sale_en_la_evidencia_de_una_respuesta(db, stack):
    a, ca = _user(db)
    b, cb = _user(db)
    stack.llm.content["RAFAEL"] = "Respuesta de B."
    out_b = _chat_agent(stack, b, "rafael", "cuanto iva pago")
    foreign = of_kind(out_b, "document")[0]["id"]
    # un handler que devolviera por error el id ajeno: se relee con filtro de empresa y se descarta
    bridge = {"approval_id": None, "executed": True,
              "execution": {"metrics": {"customer_id": 10**9}, "data": {"route": {"id": 10**9}}},
              "evidence": [{"kind": "document", "id": foreign}]}
    assert jev.bridge_evidence(db, a, ca.id, bridge) == []
    assert jev.evidence_item(db, a, ca.id, "document", foreign) is None
    assert jev.evidence_item(db, b, cb.id, "document", foreign)["id"] == foreign
    assert jev.load_resource(db, a, None, "document", str(foreign)) is None  # sin empresa: nada


# ----------------------------------------------------------------------------- next_step nulo
def test_next_step_null_cuando_no_procede(db, stack):
    u, co = _user(db)
    use_model(stack, classifier(step("RAFAEL", "consulta", "Calcular el IVA"),
                                step("AFRODITA", "consulta", "Resumir los turnos")))
    out = say(stack, u, "calcula el iva y resume los turnos")
    assert out["success"] is True and out["next_step"] is None
    assert "approval" not in kinds(out) and "document" not in kinds(out)
    assert kinds(out) == ["audit"]
    # pregunta de aclaracion: la pregunta ya es el siguiente paso
    stack.mp.setattr(mc, "get_client", lambda: None)
    q = say(stack, u, "crea el cliente Ana López", thread="t-q")
    assert q["needs_clarification"] is True and q["next_step"] is None
    cont = [r for r in rows(db, co.id, step="CONTINUAR") if r.details.get("correlation_id") == q["request_id"]]
    assert cont and cont[0].details["next_step_type"] is None

