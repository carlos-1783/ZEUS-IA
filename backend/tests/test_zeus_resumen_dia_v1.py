"""Cierre JARVIS / Tarea 2 — el resumen del día de ZEUS recibe las ventas, el arqueo y las facturas de HOY.

«hazme el resumen del día», «¿qué ha pasado hoy?», «resumen de hoy» no son una lectura determinista: van a
la charla del modelo de ZEUS CORE. Antes el modelo solo recibía `zeus_global_context` (clientes, sesión,
módulos) y contestaba «ninguna actividad» con ventas y arqueo registrados. Ahora el contexto lleva la
actividad de hoy calculada con las lecturas reales de RAFAEL (`daily_close_summary`, `invoices_day_summary`),
solo de la empresa de la sesión y del día local Europe/Madrid, con 0 explícito si no hay nada.

Datos sembrados: dos empresas, ventas/arqueo/facturas de HOY y de AYER. Por HTTP con login real
(/api/v1/auth/login -> Bearer) y el runtime real; solo se sustituye el cliente de OpenAI (sin red) para
capturar el prompt que recibe el modelo."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.agent_activity import AgentActivity
from app.models.erp import Invoice, InvoiceStatus, InvoiceType
from app.models.fiscal import TPVSale
from app.models.tpv_cash_closure import TPVCashClosure
from services import rafael_daily_reads_v1 as rafael_reads
from services.local_day_v1 import day_bounds_utc, today_local
from services.zeus_global_context import TODAY_ACTIVITY_KEY, build_today_activity

from test_jarvis_acciones_ops_v1 import _env, _user, client, db  # noqa: F401
from test_jarvis_conversacion_real_v1 import MODEL_REPLY, llm  # noqa: F401

JARVIS = "/api/v1/jarvis/message"
SUMMARY_MSGS = ["hazme el resumen del día", "¿qué ha pasado hoy?", "resumen de hoy"]


# ----------------------------------------------------------------------------- datos sembrados
def _today_mid():
    """Instante de HOY (día local) ya pasado: mitad entre el inicio del día local y ahora."""
    start, _ = day_bounds_utc(today_local())
    return start + (datetime.now(timezone.utc) - start) / 2


def _yesterday_mid():
    start, end = day_bounds_utc(today_local() - timedelta(days=1))
    return start + (end - start) / 2


def _sale(db, user, cid, when, total, method="efectivo"):
    base = round(total / 1.1, 2)
    db.add(TPVSale(user_id=user.id, company_id=cid, ticket_id=f"T-{uuid.uuid4().hex[:10]}", document_type="ticket",
                   sale_date=when, payment_method=method, subtotal=Decimal(str(base)),
                   tax_amount=Decimal(str(round(total - base, 2))), total=Decimal(str(total))))
    db.commit()


def _closure(db, user, cid, when, counted, expected):
    db.add(TPVCashClosure(company_id=cid, user_id=user.id, terminal_id="T1", period_start=when - timedelta(hours=1),
                          period_end=when, sales_count=1, cash_sales_total=Decimal("0"),
                          card_sales_total=Decimal("0"), other_sales_total=Decimal("0"),
                          sales_total=Decimal("0"), initial_cash=Decimal("100"), final_cash=Decimal(counted),
                          expected_cash=Decimal(expected),
                          difference=Decimal(str(Decimal(counted) - Decimal(expected))),
                          status="ok" if counted == expected else "discrepancy"))
    db.commit()


def _invoice(db, cid, when, total):
    db.add(Invoice(invoice_number=f"F-{uuid.uuid4().hex[:10]}", company_id=cid, status=InvoiceStatus.SENT,
                   total=total, tax_amount=round(total - total / 1.21, 2), amount_paid=0.0,
                   issue_date=when.replace(tzinfo=None), invoice_type=InvoiceType.INVOICE))
    db.commit()


def _seed_two_companies(db):
    """A: hoy 2 ventas (11,00 efectivo + 22,00 tarjeta), arqueo contado 141,00 (esperado 142,00) y una
    factura de 60,50; ayer 84,70 de venta, arqueo 555,00 y factura 707,00. B: hoy 330,00, arqueo 999,00 y
    factura 444,00. Importes distintos para poder afirmar que NO aparecen."""
    ua, ca = _user(db)
    ub, cb = _user(db)
    now, yest = _today_mid(), _yesterday_mid()
    _sale(db, ua, ca.id, now, 11.0, "efectivo")
    _sale(db, ua, ca.id, now, 22.0, "tarjeta")
    _closure(db, ua, ca.id, now, "141", "142")
    _invoice(db, ca.id, now, 60.5)
    _sale(db, ua, ca.id, yest, 84.7)
    _closure(db, ua, ca.id, yest, "555", "555")
    _invoice(db, ca.id, yest, 707.0)
    _sale(db, ub, cb.id, now, 330.0)
    _closure(db, ub, cb.id, now, "999", "999")
    _invoice(db, cb.id, now, 444.0)
    return (ua, ca), (ub, cb)


FOREIGN = ("84,70", "555,00", "707,00", "330,00", "999,00", "444,00")


def _assert_today_a(text):
    assert f"Actividad de hoy {today_local().isoformat()}" in text, text
    assert "2 ventas TPV (33,00 €)" in text and "1 facturas emitidas (60,50 €)" in text, text
    assert "2 tickets, total 33,00 €" in text, text
    assert "efectivo 11,00 € (1)" in text and "tarjeta 22,00 € (1)" in text, text
    assert "Arqueo de caja: 1 cierre(s), efectivo contado 141,00 €, descuadre -1,00 €" in text, text
    assert "60,50 €" in text and "no inventes otras" in text, text
    for frag in FOREIGN:  # ni lo de ayer ni lo de la otra empresa
        assert frag not in text, (frag, text)


# ----------------------------------------------------------------------------- lectura (sin HTTP)
def test_actividad_de_hoy_solo_hoy_y_solo_su_empresa(db):
    (ua, ca), (ub, cb) = _seed_two_companies(db)
    text_a, stats_a = build_today_activity(db, ca.id, {"tpv": True})
    _assert_today_a(text_a)
    assert stats_a == {"tickets": 2, "cash_closures": 1, "available": True,
                       "date": today_local().isoformat(), "invoices": 1}
    text_b, _ = build_today_activity(db, cb.id, {"tpv": True})
    assert "1 ventas TPV (330,00 €)" in text_b and "999,00 €" in text_b and "444,00 €" in text_b
    assert "33,00" not in text_b and "141,00" not in text_b and "60,50" not in text_b


def test_reutiliza_las_lecturas_de_rafael(db):
    """Mismas cifras que el cierre de hoy y las facturas de hoy de RAFAEL (no hay un cálculo paralelo)."""
    (ua, ca), _ = _seed_two_companies(db)
    close = rafael_reads.daily_close_summary(db, ca.id, today_local())
    inv = rafael_reads.invoices_day_summary(db, ca.id, today_local())
    text, _ = build_today_activity(db, ca.id, {"tpv": True})
    assert close["tickets"] == 2 and close["total"] == 33.0 and inv["count"] == 1
    assert f"{close['tickets']} ventas TPV (33,00 €)" in text


def test_empresa_vacia_dice_cero_sin_inventar(db):
    _seed_two_companies(db)  # hay datos de otras empresas: no deben aparecer
    _, cv = _user(db)
    text, stats = build_today_activity(db, cv.id, {"tpv": True})
    assert "0 ventas TPV (0,00 €), 0 facturas emitidas (0,00 €)" in text, text
    assert "No hay ventas TPV registradas" in text and "0 facturas" in text
    assert "no se hizo arqueo de caja" in text
    assert stats["tickets"] == 0 and stats["invoices"] == 0 and stats["cash_closures"] == 0
    for frag in FOREIGN + ("33,00", "141,00", "60,50"):
        assert frag not in text, frag


def test_sin_modulo_tpv_no_da_ventas_y_lo_dice(db):
    _, cv = _user(db, company_type="office")
    text, stats = build_today_activity(db, cv.id, {"tpv": False})
    assert "ventas TPV: sin módulo TPV" in text and "no tiene activo el módulo TPV" in text
    assert stats["tickets"] is None and "0 facturas emitidas" in text


def test_sin_empresa_o_error_de_lectura_no_da_un_cero_falso(db, monkeypatch):
    text, stats = build_today_activity(db, None, {"tpv": True})
    assert stats == {"available": False, "reason": "no_company"} and "no des cifras" in text
    _, c = _user(db)

    def boom(*a, **k):
        raise RuntimeError("bd caida")

    monkeypatch.setattr(rafael_reads, "daily_close_summary", boom)
    text, stats = build_today_activity(db, c.id, {"tpv": True})
    assert stats == {"available": False, "reason": "read_error"}
    assert "no se ha podido leer" in text and "0 ventas" not in text


# ----------------------------------------------------------------------------- HTTP con login real
def _token(client, user):
    r = client.post("/api/v1/auth/login", data={"username": user.email, "password": "TestPass1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _post(client, headers, message):
    r = client.post(JARVIS, json={"message": message, "thread_id": f"t-{uuid.uuid4().hex[:8]}"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _prompt_text(call):
    return "\n".join(m["content"] for m in call["messages"] if m["role"] == "user")


def _count_reads(monkeypatch):
    """Cuenta las lecturas reales de RAFAEL que hace la actividad de hoy (sin cambiar su resultado)."""
    n = {"close": 0, "inv": 0}
    real_close, real_inv = rafael_reads.daily_close_summary, rafael_reads.invoices_day_summary

    def close(*a, **k):
        n["close"] += 1
        return real_close(*a, **k)

    def inv(*a, **k):
        n["inv"] += 1
        return real_inv(*a, **k)

    monkeypatch.setattr(rafael_reads, "daily_close_summary", close)
    monkeypatch.setattr(rafael_reads, "invoices_day_summary", inv)
    return n


def _turn_logs(db, company_id, request_id):
    """Pasos de la cadena de ESE turno (misma correlacion que el request_id de la respuesta)."""
    db.expire_all()
    rows = db.query(AgentActivity).filter(AgentActivity.company_id == company_id).all()
    return [r for r in rows if (r.details or {}).get("correlation_id") == request_id]


def _today_logs(rows):
    return [r for r in rows if (r.details or {}).get("action") == "load_today_activity"
            or "today_activity" in (r.details or {})]


@pytest.mark.parametrize("msg", SUMMARY_MSGS)
def test_resumen_del_dia_por_jarvis_el_modelo_recibe_las_cifras_de_hoy(db, client, llm, monkeypatch, msg):
    (ua, ca), (ub, cb) = _seed_two_companies(db)
    reads = _count_reads(monkeypatch)
    out = _post(client, _token(client, ua), msg)
    assert out["success"] and out["message"] == MODEL_REPLY and not out.get("executed_action"), out
    assert len(llm.calls) == 1
    prompt = _prompt_text(llm.calls[0])
    assert TODAY_ACTIVITY_KEY in prompt and "_today_activity_provider" not in prompt
    _assert_today_a(prompt)
    assert reads == {"close": 1, "inv": 1}  # una lectura de cada, solo porque contesta ZEUS
    # registro verificable del turno: CONTEXTO/load_today_activity con lo que se paso al modelo
    logs = _today_logs(_turn_logs(db, ca.id, out["request_id"]))
    assert len(logs) == 1, [r.details for r in logs]
    row = logs[0]
    assert row.action_type == "chain_contexto" and row.details["action"] == "load_today_activity"
    assert row.status == "success" and row.agent_name == "ZEUS CORE"
    assert row.details["today_activity"] == {"tickets": 2, "cash_closures": 1, "available": True,
                                             "date": today_local().isoformat(), "invoices": 1}


def test_resumen_del_dia_por_jarvis_cada_empresa_lo_suyo_y_la_vacia_cero(db, client, llm):
    (ua, ca), (ub, cb) = _seed_two_companies(db)
    uv, _ = _user(db)
    _post(client, _token(client, ub), "resumen de hoy")
    _post(client, _token(client, uv), "¿qué ha pasado hoy?")
    pb, pv = _prompt_text(llm.calls[0]), _prompt_text(llm.calls[1])
    assert "1 ventas TPV (330,00 €)" in pb and "999,00 €" in pb and "444,00 €" in pb
    assert "33,00" not in pb and "141,00" not in pb and "60,50" not in pb
    assert "0 ventas TPV (0,00 €), 0 facturas emitidas (0,00 €)" in pv
    for frag in FOREIGN + ("33,00", "141,00", "60,50"):
        assert frag not in pv, frag


def test_jarvis_sin_credenciales_no_responde(client, llm):
    r = client.post(JARVIS, json={"message": "resumen de hoy"})
    assert r.status_code == 401, r.text
    assert not llm.calls


def test_consulta_determinista_y_bloqueo_legal_no_cambian(db, client, llm):
    """El cierre de hoy sigue siendo la lectura de RAFAEL (sin modelo) y el trámite AEAT sigue bloqueado."""
    (ua, ca), _ = _seed_two_companies(db)
    h = _token(client, ua)
    out = _post(client, h, "cierre de hoy")
    assert out["executed_action"] and out["execution"]["intent"] == "get_daily_close"
    assert out["execution"]["metrics"]["total"] == 33.0
    blk = _post(client, h, "presenta el IVA del trimestre")
    assert blk["status"] == "blocked_legal" and not blk.get("executed_action")
    assert not llm.calls


def test_zeus_delega_no_lee_ni_registra_la_actividad_de_hoy(db, client, llm, monkeypatch):
    """Charla que ZEUS enruta a RAFAEL/PERSEO (route_message): contesta el agente delegado (su system prompt),
    su prompt NO lleva today_activity, NO se hace ninguna lectura y el log del turno no la menciona. Cuando
    contesta el propio ZEUS (_handle_directly): una lectura de cada y su registro."""
    from services.agent_routing import route_message
    from test_jarvis_conversacion_real_v1 import _prompts

    prompts = _prompts()
    (ua, ca), _ = _seed_two_companies(db)
    h = _token(client, ua)
    reads = _count_reads(monkeypatch)
    for msg, agent in (("explícame qué es el IVA", "RAFAEL"),
                       ("¿qué opinas de mi estrategia de marketing en redes?", "PERSEO")):
        assert route_message(msg).agent == agent
        out = _post(client, h, msg)
        assert out["success"] and not out.get("executed_action"), out
        call = llm.calls[-1]
        assert call["messages"][0]["content"] == prompts[agent], msg  # contesto el delegado
        p = _prompt_text(call)
        assert "zeus_global_context" in p and TODAY_ACTIVITY_KEY not in p and "33,00" not in p, msg
        assert reads == {"close": 0, "inv": 0}, (msg, reads)
        turn = _turn_logs(db, ca.id, out["request_id"])
        assert turn and not _today_logs(turn), (msg, [r.details for r in turn])
    out = _post(client, h, "resumen de hoy")  # sin agente claro: contesta ZEUS CORE
    call = llm.calls[-1]
    assert call["messages"][0]["content"] == prompts["ZEUS CORE"]
    assert TODAY_ACTIVITY_KEY in _prompt_text(call) and "2 ventas TPV (33,00 €)" in _prompt_text(call)
    assert reads == {"close": 1, "inv": 1}
    logs = _today_logs(_turn_logs(db, ca.id, out["request_id"]))
    assert len(logs) == 1 and logs[0].details["today_activity"]["tickets"] == 2


def test_prelanzamiento_de_superusuario_no_lee_la_actividad_de_hoy(db, client, llm, monkeypatch):
    """Camino de pre-lanzamiento (zeus_core: superusuario + «pre-lanzamiento»): ni lectura ni registro."""
    from services.zeus_global_context import TODAY_ACTIVITY_PROVIDER_KEY

    import agents.zeus_core as zc

    seen = []
    monkeypatch.setattr(zc.ZeusCore, "_start_prelaunch_phase",
                        lambda self, ctx: seen.append(callable(ctx.get(TODAY_ACTIVITY_PROVIDER_KEY)))
                        or {"success": True, "content": "plan pre-lanzamiento"})
    su, sc = _user(db, superuser=True)
    reads = _count_reads(monkeypatch)
    out = _post(client, _token(client, su), "pre-lanzamiento")
    assert out["success"] and out["message"] == "plan pre-lanzamiento", out
    assert seen == [True] and reads == {"close": 0, "inv": 0} and not llm.calls
    assert not _today_logs(_turn_logs(db, sc.id, out["request_id"]))


def test_with_today_activity_no_muta_el_contexto_y_falla_sin_cero_falso():
    from agents.zeus_core import _with_today_activity
    from services.zeus_global_context import TODAY_ACTIVITY_PROVIDER_KEY

    ctx = {"zeus_global_context": {"company_id": 1}, TODAY_ACTIVITY_PROVIDER_KEY: lambda: "HOY: 3 ventas"}
    out = _with_today_activity(ctx)
    assert out["zeus_global_context"] == {"company_id": 1, TODAY_ACTIVITY_KEY: "HOY: 3 ventas"}
    assert TODAY_ACTIVITY_PROVIDER_KEY not in out and TODAY_ACTIVITY_KEY not in ctx["zeus_global_context"]
    plain = {"zeus_global_context": {"company_id": 1}}
    assert _with_today_activity(plain) is plain

    def boom():
        raise RuntimeError("x")

    out = _with_today_activity({"zeus_global_context": {}, TODAY_ACTIVITY_PROVIDER_KEY: boom})
    assert "no se ha podido leer" in out["zeus_global_context"][TODAY_ACTIVITY_KEY]


def test_otros_agentes_no_reciben_la_actividad_de_hoy(db, client, llm, monkeypatch):
    """Solo la charla de ZEUS CORE: el chat de PERSEO no gasta tokens ni lecturas en esto."""
    (ua, ca), _ = _seed_two_companies(db)
    reads = _count_reads(monkeypatch)
    r = client.post("/api/v1/chat/perseo/chat", json={"message": "hola, ¿qué tal?", "thread_id": "t-p"},
                    headers=_token(client, ua))
    assert r.status_code == 200, r.text
    assert llm.calls and TODAY_ACTIVITY_KEY not in _prompt_text(llm.calls[-1])
    assert reads == {"close": 0, "inv": 0}
