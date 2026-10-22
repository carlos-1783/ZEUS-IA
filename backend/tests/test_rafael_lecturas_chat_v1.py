"""RAFAEL en el chat: «última factura», «facturas de hoy», «IVA del trimestre» y «¿cuánto llevo hoy?».

Lecturas reales de la BD (solo la empresa de la sesión), por el ejecutor (guard THALOS, módulo, registro)
y por el endpoint HTTP del chat del propio agente (/chat/rafael/chat) sin llegar al LLM (run_chat es un
stub que delata si se le llamó). El IVA trimestral reutiliza el cálculo de /tpv/fiscal/quarterly-vat y no
envía nada a la AEAT.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.models.agent_activity import AgentActivity
from app.models.customer import Customer
from app.models.erp import Invoice, InvoiceStatus, InvoiceType
from app.models.fiscal import TPVSale, TPVSaleItem
from app.schemas.zeus_action import ZeusAction
from services import jarvis_ops_actions as ops
from services.intent_parser import parse_intent
from services.local_day_v1 import day_bounds_utc, today_local
from services.tpv_quarterly_vat_v1 import quarter_bounds

from test_fase2_step1_chat_e2e_v1 import LLM_STUB, agent_say
from test_jarvis_acciones_ops_v1 import _env, _user, client, db, say  # noqa: F401


# ----------------------------------------------------------------------------- datos sembrados
def _inv(db, cid, total, *, status=InvoiceStatus.SENT, when=None, tax=None, paid=0.0, customer_id=None,
         itype=InvoiceType.INVOICE):
    inv = Invoice(invoice_number=f"F-{uuid.uuid4().hex[:10]}", company_id=cid, status=status, total=total,
                  tax_amount=tax if tax is not None else round(total - total / 1.21, 2), amount_paid=paid,
                  issue_date=when or datetime.utcnow(), customer_id=customer_id, invoice_type=itype)
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def _sale(db, user, cid, when, items, method="efectivo"):
    """items: [(base, tipo, cuota)]. Total = base + cuota (snapshots fiscales como el TPV)."""
    total = sum(b + q for b, _, q in items)
    s = TPVSale(user_id=user.id, company_id=cid, ticket_id=f"T-{uuid.uuid4().hex[:10]}", document_type="ticket",
                sale_date=when, payment_method=method, subtotal=Decimal(str(sum(b for b, _, _ in items))),
                tax_amount=Decimal(str(sum(q for _, _, q in items))), total=Decimal(str(round(total, 2))))
    db.add(s)
    db.flush()
    for b, rate, q in items:
        db.add(TPVSaleItem(tpv_sale_id=s.id, product_id="p1", product_name="Caña", quantity=Decimal("1"),
                           unit_price=Decimal(str(b)), tax_rate_snapshot=Decimal(str(rate)),
                           tax_amount=Decimal(str(q)), base_amount=Decimal(str(b))))
    db.commit()
    return s


def _today_start_naive_utc():
    start, _ = day_bounds_utc(today_local())
    return start.replace(tzinfo=None)


def _read(db, user, cid, action, payload=None, mods=None):
    act = ZeusAction(action_type=action, company_id=cid, user_id=user.id, payload=payload or {})
    with patch("services.module_gate.active_modules", return_value=mods or {"tpv": True}):
        return asyncio.run(ops.run_read_action(db, user, act))


def _cur_quarter():
    t = today_local()
    return t.year, (t.month - 1) // 3 + 1


# ----------------------------------------------------------------------------- intencion (reglas)
@pytest.mark.parametrize("msg,intent,meta", [
    ("muéstrame la última factura", "get_last_invoice", {}),
    ("enséñame la ultima factura", "get_last_invoice", {}),
    ("¿cuál es la última factura?", "get_last_invoice", {}),
    ("dime la ULTIMA factura", "get_last_invoice", {}),
    ("la última factura", "get_last_invoice", {}),
    ("facturas de hoy", "get_invoices_today", {}),
    ("enséñame las facturas de hoy", "get_invoices_today", {}),
    ("¿qué facturas he hecho hoy?", "get_invoices_today", {}),
    ("dime las facturas emitidas hoy", "get_invoices_today", {}),
    ("IVA del trimestre", "get_vat_quarter", {"quarter_ref": "current"}),
    ("¿cuál es el IVA de este trimestre?", "get_vat_quarter", {"quarter_ref": "current"}),
    ("dime el iva trimestral", "get_vat_quarter", {"quarter_ref": "current"}),
    ("¿cuánto IVA llevo este trimestre?", "get_vat_quarter", {"quarter_ref": "current"}),
    ("¿cuánto IVA tengo que pagar este trimestre?", "get_vat_quarter", {"quarter_ref": "current"}),
    ("el IVA del trimestre pasado", "get_vat_quarter", {"quarter_ref": "previous"}),
    ("iva del primer trimestre de 2026", "get_vat_quarter", {"quarter": 1, "year": 2026}),
    ("¿cuánto llevo hoy?", "tpv_sales_today", {"period": "today", "days": 1}),
    ("cuanto llevamos hoy", "tpv_sales_today", {"period": "today", "days": 1}),
    ("¿cuánto he facturado hoy?", "tpv_sales_today", {"period": "today", "days": 1}),
    ("cierre de hoy", "get_daily_close", {"day": "today"}),
])
def test_frases_naturales_se_entienden(msg, intent, meta):
    t = parse_intent(msg)
    assert t.intent == intent and not t.needs_clarification and t.confidence >= 0.7, (msg, t.intent, t.metadata)
    for k, v in meta.items():
        assert t.metadata.get(k) == v, (msg, t.metadata)


@pytest.mark.parametrize("msg", [
    # escrituras/tramites: no son consultas (nada se presenta ni se envia por una lectura)
    "presenta el IVA del trimestre", "envía la última factura a Juan", "anula la última factura",
    "crea las facturas de hoy", "prepara la factura y el IVA del trimestre",
    # conversacion / explicacion y frases compuestas de los planes multiagente
    "explícame el IVA trimestral", "explícame qué es el IVA", "cuanto iva pago",
    "dime cuánto IVA pago este trimestre y redacta un borrador de correo a mi gestor",
    "calcula el IVA y la factura del trimestre",
    # horas trabajadas, no ventas
    "cuánto llevo hoy trabajando",
])
def test_lo_que_no_es_esta_consulta_no_la_dispara(msg):
    assert parse_intent(msg).intent not in ("get_last_invoice", "get_invoices_today", "get_vat_quarter",
                                            "tpv_sales_today"), msg


# Ordenes (revision): ninguna puede acabar en una lectura. Lista blanca de marco de consulta.
ORDENES_FACTURA = [
    "cancela la última factura", "marca la última factura como cobrada", "sube la última factura a Verifactu",
    "factura hoy 50 euros a Juan", "hazle la factura de hoy a Bar Pepe", "registra las facturas de hoy",
    "cancela las facturas de hoy", "comparte la última factura con mi gestor", "devuelve la última factura",
    "quita la última factura", "firma la última factura", "muéstrame la última factura y envíasela a Juan",
]
ORDENES_IVA = [
    "aplaza el IVA del trimestre", "ingresa el IVA del trimestre", "fracciona el IVA del trimestre",
    "domicilia el IVA del trimestre", "presenta el IVA del trimestre",
]
LECTURAS = ("get_last_invoice", "get_invoices_today", "get_vat_quarter")


@pytest.mark.parametrize("msg", ORDENES_FACTURA + ORDENES_IVA)
def test_una_orden_nunca_es_una_lectura(msg):
    assert parse_intent(msg).intent not in LECTURAS, msg


@pytest.mark.parametrize("msg", [
    "quiero ver la última factura", "oye rafael, ¿me puedes enseñar las facturas de hoy?",
    "consulta la última factura", "dame las facturas de hoy", "¿cuál es el IVA del trimestre pasado?",
])
def test_marcos_de_consulta_siguen_siendo_lectura(msg):
    t = parse_intent(msg)
    assert t.intent in LECTURAS and not t.needs_clarification, (msg, t.intent)


@pytest.mark.parametrize("msg,reason", [
    ("sube la última factura a Verifactu", "aeat_submission"),
    ("envía las facturas de hoy a Hacienda", "aeat_submission"),
    ("por favor, manda la factura a la AEAT", "aeat_submission"),
    ("aplaza el IVA del trimestre", "tax_filing"), ("ingresa el IVA del trimestre", "tax_filing"),
    ("fracciona el IVA del trimestre", "tax_filing"), ("domicilia el IVA del trimestre", "tax_filing"),
    ("presenta el modelo 303", "tax_filing"), ("quiero que presentes el IVA", "tax_filing"),
])
def test_guardarrail_legal_reconoce_ordenes(msg, reason):
    from services.jarvis_legal_block import legal_block

    blk = legal_block(msg)
    assert blk is not None and blk[0] == reason, (msg, blk)


@pytest.mark.parametrize("msg", [
    "¿cuándo presento el modelo 303 a Hacienda?", "¿cuánto IVA tengo que pagar este trimestre?",
    "paga la factura del proveedor con IVA", "envía un correo a mi gestor sobre Hacienda",
    "aplaza el envío de la oferta a los clientes", "IVA del trimestre", "muéstrame la última factura",
])
def test_guardarrail_legal_no_bloquea_preguntas_ni_otras_cosas(msg):
    from services.jarvis_legal_block import legal_block

    assert legal_block(msg) is None, msg


def test_negacion_no_ejecuta_pregunta():
    t = parse_intent("no me enseñes la última factura")
    assert t.needs_clarification and "explicit_intent" in t.missing_entities


def test_pendientes_sigue_siendo_pendientes():
    assert parse_intent("última factura pendiente").intent == "get_pending_invoices"
    assert parse_intent("facturas pendientes").intent == "get_pending_invoices"


# ----------------------------------------------------------------------------- ejecutor (datos reales)
def test_ultima_factura_real_y_aislada(db):
    u, c = _user(db)
    ou, other = _user(db)
    cust = Customer(name="Bar Pepe", company_id=c.id)
    db.add(cust)
    db.commit()
    _inv(db, c.id, 50.0, when=datetime.utcnow() - timedelta(days=3))
    last = _inv(db, c.id, 121.0, tax=21.0, when=datetime.utcnow() - timedelta(hours=1), customer_id=cust.id,
                paid=21.0)
    _inv(db, c.id, 999.0, when=datetime.utcnow(), itype=InvoiceType.ESTIMATE)  # presupuesto: no es factura
    _inv(db, other.id, 777.0, when=datetime.utcnow())  # otra empresa: no se ve
    r = _read(db, u, c.id, "get_last_invoice")
    assert r.success and r.executed
    inv = r.metrics["invoice"]
    assert inv["invoice_number"] == last.invoice_number and inv["amount_total"] == 121.0
    assert inv["customer"] == "Bar Pepe" and inv["amount_due"] == 100.0 and inv["status"] == "sent"
    assert r.metrics["invoices_count"] == 2
    assert last.invoice_number in r.message and "121,00 €" in r.message and "777" not in r.message
    log = (db.query(AgentActivity)
           .filter(AgentActivity.company_id == c.id, AgentActivity.action_type == "agent_action_get_last_invoice")
           .order_by(AgentActivity.id.desc()).first())
    assert log is not None and log.status == "completed" and log.agent_name == "RAFAEL"


def test_ultima_factura_sin_facturas_es_un_dato(db):
    u, c = _user(db)
    r = _read(db, u, c.id, "get_last_invoice")
    assert r.success and r.executed and r.metrics["found"] is False
    assert r.message == "No hay facturas todavía en tu empresa."


def test_facturas_de_hoy_reales_y_aisladas(db):
    u, c = _user(db)
    ou, other = _user(db)
    a = _inv(db, c.id, 100.0, tax=10.0)
    b = _inv(db, c.id, 50.0, tax=5.0, status=InvoiceStatus.PAID, paid=50.0)
    _inv(db, c.id, 30.0, status=InvoiceStatus.DRAFT)  # borrador: se cuenta aparte
    _inv(db, c.id, 80.0, status=InvoiceStatus.VOID)  # anulada: no suma
    _inv(db, c.id, 400.0, when=_today_start_naive_utc() - timedelta(minutes=30))  # ayer (dia local)
    _inv(db, other.id, 999.0)  # otra empresa
    r = _read(db, u, c.id, "get_invoices_today")
    assert r.success and r.executed
    m = r.metrics
    assert m["date"] == today_local().isoformat()
    assert m["count"] == 2 and m["amount_total"] == 150.0 and m["tax_total"] == 15.0
    assert m["drafts_count"] == 1 and m["void_count"] == 1
    nums = {i["invoice_number"] for i in m["invoices"]}
    assert {a.invoice_number, b.invoice_number} <= nums and len(nums) == 4
    assert "150,00 €" in r.message and "999" not in r.message and "400" not in r.message


def test_facturas_de_hoy_vacio_es_cero(db):
    u, c = _user(db)
    _inv(db, c.id, 400.0, when=_today_start_naive_utc() - timedelta(minutes=30))  # solo ayer
    r = _read(db, u, c.id, "get_invoices_today")
    assert r.success and r.metrics["count"] == 0 and "0 facturas" in r.message


def test_iva_trimestre_reutiliza_el_calculo_del_tpv_y_aislado(db):
    u, c = _user(db)
    ou, other = _user(db)
    now = datetime.now(timezone.utc)
    q_start, _ = quarter_bounds(*_cur_quarter())
    _sale(db, u, c.id, now, [(3.0, 0.10, 0.30), (2.5, 0.21, 0.52)])
    _sale(db, u, c.id, now, [(10.0, 0.04, 0.40)])
    _sale(db, u, c.id, q_start.replace(tzinfo=timezone.utc) - timedelta(days=5), [(500.0, 0.21, 105.0)])  # trim. anterior
    _sale(db, ou, other.id, now, [(900.0, 0.21, 189.0)])  # otra empresa
    r = _read(db, u, c.id, "get_vat_quarter", {"quarter_ref": "current"})
    assert r.success and r.executed
    m = r.metrics
    assert (m["year"], m["quarter"]) == _cur_quarter()
    rates = {r["rate"]: (r["tax_base"], r["vat_amount"]) for r in m["by_rate"]}
    assert m["sales_count"] == 2 and m["period_label"] == f"{m['quarter']}T {m['year']}"
    assert rates == {"4 %": (10.0, 0.40), "10 %": (3.0, 0.30), "21 %": (2.5, 0.52)}
    assert m["vat_total"] == 1.22 and m["grand_total"] == 16.72
    assert m["submitted_to_aeat"] is False and "no se ha presentado" in r.message
    assert "1,22 €" in r.message and "189" not in r.message
    # trimestre anterior: solo la venta de 500 €
    p = _read(db, u, c.id, "get_vat_quarter", {"quarter_ref": "previous"})
    assert p.success and p.metrics["sales_count"] == 1 and p.metrics["by_rate"][2]["vat_amount"] == 105.0


def test_iva_trimestre_coincide_con_el_endpoint(db, client):
    """Mismo calculo que GET /tpv/fiscal/quarterly-vat (para una empresa sin ventas legado)."""
    from app.core.auth import get_current_active_user
    from app.main import app

    u, c = _user(db)
    _sale(db, u, c.id, datetime.now(timezone.utc), [(3.0, 0.10, 0.30), (2.5, 0.21, 0.52)])
    y, q = _cur_quarter()
    app.dependency_overrides[get_current_active_user] = lambda: u
    ep = client.get("/api/v1/tpv/fiscal/quarterly-vat", params={"year": y, "quarter": q})
    assert ep.status_code == 200, ep.text
    r = _read(db, u, c.id, "get_vat_quarter", {"quarter": q, "year": y})
    e = ep.json()
    for row, n in zip(r.metrics["by_rate"], (4, 10, 21)):
        assert (row["tax_base"], row["vat_amount"]) == (e[f"base_{n}"], e[f"iva_{n}"]), n
    assert r.metrics["recargo_total"] == e["recargo_total"] and r.metrics["grand_total"] == e["grand_total"]
    assert "sales_count" not in ep.json()  # la respuesta del endpoint no cambia


def test_iva_trimestre_vacio_y_periodo_invalido_y_modulo(db):
    u, c = _user(db)
    r = _read(db, u, c.id, "get_vat_quarter")
    assert r.success and r.metrics["sales_count"] == 0 and r.metrics["vat_total"] == 0
    assert r.message.startswith("No hay ventas TPV registradas") and "0,00 €" in r.message
    for bad in ({"quarter": 5}, {"quarter": 1, "year": 2999}, {"quarter_ref": "siguiente"},
                {"quarter_ref": "explicit"}, {"quarter": "x"}):
        b = _read(db, u, c.id, "get_vat_quarter", bad)
        assert b.success is False and b.executed is False and "Trimestre no válido" in b.message, bad
    blocked = _read(db, u, c.id, "get_vat_quarter", mods={"tpv": False})
    assert blocked.success is False and "TPV" in blocked.message


def test_lecturas_rafael_rechazadas_con_otro_agente(db):
    from services.zeus_agent_executor_v1 import execute_agent_action

    u, _ = _user(db)
    for a in ("get_last_invoice", "get_invoices_today", "get_vat_quarter"):
        r = asyncio.run(execute_agent_action(db, user=u, agent="PERSEO", action=a, payload={}))
        assert r["success"] is False and r["status"] == "agent_mismatch", a


# ----------------------------------------------------------------------------- HTTP: chat de RAFAEL
def test_chat_rafael_ultima_factura_no_llega_al_llm(db, client):
    u, c = _user(db)
    inv = _inv(db, c.id, 60.5)
    out = agent_say(client, u, "rafael", "muéstrame la última factura")
    assert out["message"] != LLM_STUB and out["success"] and out["executed_action"]
    assert out["intent"] == "get_last_invoice" and inv.invoice_number in out["message"]
    assert out["execution"]["metrics"]["invoice"]["amount_total"] == 60.5


def test_chat_rafael_facturas_de_hoy_y_aislamiento(db, client):
    ua, ca = _user(db)
    ub, cb = _user(db)
    _inv(db, ca.id, 20.0)
    _inv(db, cb.id, 555.0)
    oa = agent_say(client, ua, "rafael", "enséñame las facturas de hoy")
    ob = agent_say(client, ub, "rafael", "facturas de hoy")
    assert oa["intent"] == ob["intent"] == "get_invoices_today"
    assert oa["execution"]["metrics"]["count"] == 1 and oa["execution"]["metrics"]["amount_total"] == 20.0
    assert ob["execution"]["metrics"]["amount_total"] == 555.0 and "555" not in oa["message"]


def test_chat_rafael_cuanto_llevo_hoy_es_el_cierre_de_hoy(db, client):
    u, c = _user(db)
    ou, other = _user(db)
    now = datetime.now(timezone.utc)
    _sale(db, u, c.id, now, [(10.0, 0.10, 1.0)])
    _sale(db, ou, other.id, now, [(300.0, 0.10, 30.0)])
    for msg in ("¿cuánto llevo hoy?", "cierre de hoy", "¿cuánto he facturado hoy?"):
        out = agent_say(client, u, "rafael", msg)
        assert out["message"] != LLM_STUB and out["executed_action"], (msg, out)
        assert out["intent"] == "get_daily_close", (msg, out["intent"])
        m = out["execution"]["metrics"]
        assert m["date"] == today_local().isoformat() and m["tickets"] == 1 and m["total"] == 11.0, msg
        assert "11,00 €" in out["message"] and "330" not in out["message"]


def test_chat_rafael_iva_del_trimestre(db, client):
    u, c = _user(db)
    _sale(db, u, c.id, datetime.now(timezone.utc), [(100.0, 0.21, 21.0)])
    out = agent_say(client, u, "rafael", "¿cuál es el IVA de este trimestre?")
    assert out["message"] != LLM_STUB and out["executed_action"] and out["intent"] == "get_vat_quarter"
    assert out["execution"]["metrics"]["by_rate"][2]["vat_amount"] == 21.0 and "21,00 €" in out["message"]
    assert "no se ha presentado" in out["message"] and "(1 venta," in out["message"]


def test_chat_rafael_cuenta_vacia_devuelve_el_vacio_como_dato(db, client):
    u, _ = _user(db)
    expect = {
        "muéstrame la última factura": "No hay facturas todavía",
        "facturas de hoy": "0 facturas",
        "¿cuánto llevo hoy?": "No hay ventas TPV registradas",
        "IVA del trimestre": "IVA repercutido 0,00 €",
    }
    for msg, frag in expect.items():
        out = agent_say(client, u, "rafael", msg)
        assert out["message"] != LLM_STUB and out["success"] and out["executed_action"], (msg, out)
        assert frag in out["message"], (msg, out["message"])


def test_chat_rafael_lo_demas_sigue_al_modelo(db, client):
    u, _ = _user(db)
    assert agent_say(client, u, "rafael", "explícame qué es el IVA")["message"] == LLM_STUB
    assert agent_say(client, u, "rafael", "no me enseñes la última factura")["message"] == LLM_STUB
    # una lectura de RAFAEL pedida en el workspace de PERSEO no se ejecuta alli
    out = agent_say(client, u, "perseo", "muéstrame la última factura")
    assert out["message"].startswith(LLM_STUB) and not out.get("executed_action")
    # en PERSEO «¿cuánto llevo hoy?» no se reconvierte en el cierre de RAFAEL
    assert not agent_say(client, u, "perseo", "¿cuánto llevo hoy?").get("executed_action")


def test_chat_rafael_iva_bloqueado_sin_tpv(db, client):
    u, _ = _user(db, company_type="office")  # oficina: sin TPV
    out = agent_say(client, u, "rafael", "IVA del trimestre")
    assert out["success"] is False and out["status"] == "blocked_module" and out["message"] != LLM_STUB


def test_zeus_tambien_lo_ejecuta(db, client):
    u, c = _user(db)
    inv = _inv(db, c.id, 42.0)
    out = say(client, u, "muéstrame la última factura")
    assert out["success"] and out["executed_action"] and out["execution"]["intent"] == "get_last_invoice"
    assert inv.invoice_number in out["message"]


# ----------------------------------------------------------------------------- HTTP: ordenes (revision)
def _seed_reads(db, user, cid):
    _inv(db, cid, 70.0)
    _sale(db, user, cid, datetime.now(timezone.utc), [(100.0, 0.21, 21.0)])


@pytest.mark.parametrize("msg", ORDENES_FACTURA + ORDENES_IVA)
def test_orden_en_rafael_no_ejecuta_lectura(db, client, msg):
    u, c = _user(db)
    _seed_reads(db, u, c.id)
    out = agent_say(client, u, "rafael", msg)
    assert out.get("intent") not in LECTURAS and not out.get("executed_action"), (msg, out)
    assert not (out.get("execution") or {}).get("metrics"), (msg, out)


@pytest.mark.parametrize("msg", ORDENES_FACTURA + ORDENES_IVA)
def test_orden_en_zeus_no_ejecuta_lectura(db, client, msg):
    u, c = _user(db)
    _seed_reads(db, u, c.id)
    out = say(client, u, msg)
    ex = out.get("execution") or {}
    assert ex.get("intent") not in LECTURAS and not out.get("executed_action"), (msg, out)


@pytest.mark.parametrize("msg", ["sube la última factura a Verifactu"] + ORDENES_IVA)
def test_tramite_aeat_bloqueo_honesto_en_rafael_y_zeus(db, client, msg):
    u, c = _user(db)
    _seed_reads(db, u, c.id)
    for out in (agent_say(client, u, "rafael", msg), say(client, u, msg)):
        assert out["success"] is False and out["status"] == "blocked_legal", (msg, out)
        assert out["message"] != LLM_STUB and "No he" in out["message"], (msg, out["message"])
        assert not out.get("executed_action")
