"""J11: la voz es un CANAL del mismo flujo de texto, no un camino aparte. Sin red ni LLM real.

La voz se transcribe en el navegador (STT/TTS de cliente) y se envia por el mismo endpoint con
channel=voice. Aqui se prueba lo que el servidor garantiza: el canal se valida y llega a ESCUCHAR,
y un mensaje de voz con acciones con consecuencias NO se ejecuta sin confirmacion humana ni cruza
de usuario/empresa."""

from __future__ import annotations

from app.core.auth import get_current_active_user
from app.main import app
from app.models.zeus_pending_approval import ZeusPendingApproval

# fixtures y ayudantes de J8 (se importan por nombre para que pytest los use como fixtures)
from test_jarvis_comprension_v1 import (  # noqa: F401
    JARVIS, ZEUS, _chat, _llm_stub, _pending_count, _post, _rows, _seed, client, db,
)

MSG = "crea una oferta del 10% y envíala a los clientes"


def _esc(db, user, rid):
    return [r for r in _rows(db, user, rid) if r.details["chain_step"] == "ESCUCHAR"][0]


def test_voz_llega_a_escuchar_con_canal_voice_por_jarvis_y_por_chat(db, client):
    user, _ = _seed(db)
    a = _chat(client, user, "cuántos clientes tengo", url=JARVIS, thread="v-a", channel="voice")
    assert _esc(db, user, a["request_id"]).details["channel"] == "voice"
    # ruta que usa hoy el cliente web: /chat/{agente}/chat con context.channel
    b = _chat(client, user, "cuántos clientes tengo", url=ZEUS, thread="v-b", context={"channel": "voice"})
    assert _esc(db, user, b["request_id"]).details["channel"] == "voice"


def test_canal_invalido_se_rechaza_en_jarvis_y_se_normaliza_a_text_en_chat(db, client):
    user, _ = _seed(db)
    for bad in ("fax", "<script>", "VOICE ", ""):
        assert _post(client, user, JARVIS, "hola", channel=bad).status_code == 422, bad
    c = _chat(client, user, "hola", url=ZEUS, thread="v-c", context={"channel": "telepatia"})
    assert _esc(db, user, c["request_id"]).details["channel"] == "text"


def test_voz_con_accion_con_consecuencias_pide_confirmacion_y_no_ejecuta(db, client):
    user, co = _seed(db)
    out = _chat(client, user, MSG, url=JARVIS, thread="v-d", channel="voice")
    assert out["needs_confirmation"] is True and out["approval_id"]
    assert out["executed_action"] is False
    rows = db.query(ZeusPendingApproval).filter(ZeusPendingApproval.user_id == user.id).all()
    assert len(rows) == 1 and rows[0].status == "pending" and rows[0].company_id == co.id
    assert rows[0].id == out["approval_id"]
    assert _esc(db, user, out["request_id"]).details["channel"] == "voice"


def test_decir_confirmar_por_voz_de_otro_usuario_no_resuelve_la_aprobacion(db, client):
    owner, _ = _seed(db)
    other, _ = _seed(db)
    out = _chat(client, owner, MSG, url=JARVIS, thread="v-e", channel="voice")
    appr = out["approval_id"]
    # otro usuario/empresa dice «confirmar» por voz en el mismo hilo: no toca la aprobacion ajena
    _post(client, other, JARVIS, "confirmar", thread="v-e", channel="voice")
    db.expire_all()
    row = db.query(ZeusPendingApproval).filter(ZeusPendingApproval.id == appr).one()
    assert row.status == "pending" and _pending_count(db, other) == 0
    # el propietario cancelando por voz usa el mismo mecanismo que el texto
    _post(client, owner, JARVIS, "cancelar", thread="v-e", channel="voice")
    db.expire_all()
    row = db.query(ZeusPendingApproval).filter(ZeusPendingApproval.id == appr).one()
    assert row.status != "pending"


def test_build_server_context_normaliza_el_canal(db):
    from app.api.v1.endpoints.chat import build_server_context

    user, _ = _seed(db)
    assert build_server_context(db, user, {"channel": "VOICE"}, "t")["channel"] == "voice"
    assert build_server_context(db, user, {"channel": "<script>"}, "t")["channel"] == "text"
    assert "channel" not in build_server_context(db, user, {}, "t")
