"""Frases que antes acababan en el LLM: alertas de stock, facturas por periodo y órdenes sobre facturas.

- Stock («productos sin stock», «¿algo bajo mínimos?», «¿qué se ha agotado?», «¿qué me falta?», «productos con
  poco stock»…): lectura real `get_inventory_status` con foco (out/low/alerts) sobre `company_inventory_status` de
  la empresa de la sesión. Honesta: sin control de stock o sin mínimos definidos lo dice; nunca «ninguno bajo
  mínimos» cuando no hay mínimos.
- Facturas de ayer / esta semana / la semana pasada / este mes / el mes pasado: lectura real `get_invoices_period`
  con el mismo filtro por día local que «facturas de hoy» (`rafael_daily_reads_v1._invoices_between`).
- Órdenes «cancela/anula/borra/quita/rectifica/modifica/firma la factura…»: no hay acción de chat sobre facturas
  (y anular una emitida exige rectificativa; firmar exige Verifactu): bloqueo honesto con el motivo, sin lectura,
  sin LLM y sin tocar nada.
Login real (token Bearer). Otra empresa del mismo usuario y otro tenant no aparecen. El LLM (run_chat, openai) no
puede llamarse: el fixture `sin_llm` hace fallar el test.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta

import pytest

from app.models.erp import Invoice, InvoiceStatus
from services.afrodita_ops_service_v1 import (
    company_inventory_status, inventory_alerts_text, inventory_status_text,
)
from services.intent_parser import parse_intent
from services.intent_parser import product_stock_task
from services.jarvis_invoice_write_block import (
    MSG_INVOICE_NEGATED, MSG_INVOICE_RECTIFY, MSG_INVOICE_SIGN, MSG_INVOICE_VOID, invoice_order_check,
    invoice_write_block, negated_invoice_order,
)
from services.jarvis_legal_block import legal_block
from services.jarvis_ops_actions import _eur
from services.jarvis_schedule_write_block import schedule_write_block
from services.local_day_v1 import day_bounds_utc, today_local
from services.rafael_daily_reads_v1 import invoice_period_bounds
from services.zeus_agent_executor_v1 import execute_agent_action

from test_afrodita_cuadrantes_v1 import _login, _segunda_empresa, sin_llm  # noqa: F401 (autouse: sin LLM)
from test_afrodita_inventario_tpv_v1 import _erp, _tpv
from test_jarvis_acciones_ops_v1 import _env, _user, approvals, client, db, rows  # noqa: F401
from test_rafael_lecturas_chat_v1 import _inv

P = "/api/v1"

STOCK = {
    "productos sin stock": "out", "¿algo bajo mínimos?": "low", "¿qué se ha agotado?": "out",
    "¿qué me falta?": "alerts", "productos con poco stock": "low", "¿Qué productos están sin stock?": "out",
    "qué productos no tienen stock": "out", "¿hay algo agotado?": "out", "¿Hay productos bajo mínimos?": "low",
    "dime qué me falta": "alerts", "¿qué nos falta?": "alerts", "productos agotados": "out",
    "¿me dices los productos sin stock?": "out", "PRODUCTOS SIN STOCK": "out", "¿qué tengo bajo mínimos?": "low",
    "¿qué productos tienen poco stock?": "low", "¿de qué me estoy quedando sin stock?": "alerts",
    "enséñame los productos agotados": "out", "¿qué hay que reponer?": "alerts", "artículos sin stock": "out",
    "¿qué referencias están agotadas?": "out", "¿se ha agotado algo?": "out", "¿qué me queda poco?": "low",
    "¿nos falta algo?": "alerts", "¿falta algo en el almacén?": "alerts",
}
PERIODOS = {
    "facturas de ayer": "yesterday", "facturas de este mes": "month", "facturas del mes pasado": "last_month",
    "facturas de la semana": "week", "¿Qué facturas hice ayer?": "yesterday",
    "¿cuántas facturas he emitido este mes?": "month", "muéstrame las facturas de ayer": "yesterday",
    "dime las facturas del mes pasado": "last_month", "facturas de esta semana": "week",
    "¿me dices las facturas de este mes?": "month", "FACTURAS DE AYER": "yesterday",
    "las facturas de la semana pasada": "last_week", "enséñame las facturas de este mes": "month",
    "facturas emitidas ayer": "yesterday", "¿cuáles son las facturas de ayer?": "yesterday",
    "quiero ver las facturas del mes pasado": "last_month", "la factura de ayer": "yesterday",
    "listado de facturas del mes": "month", "lista de facturas de este mes": "month",
    "resumen de facturas de este mes": "month", "total de facturas del mes": "month",
    "importe de las facturas de ayer": "yesterday",
}
ORDENES = {
    "cancela la última factura": "invoice_void", "anula la factura F-2026-0001": "invoice_void",
    "firma la factura": "invoice_sign", "rectifica la última factura": "invoice_rectify",
    "borra la factura F-2026-0003": "invoice_void", "anula la última factura": "invoice_void",
    "Anula la factura 23": "invoice_void", "elimina la factura de ayer": "invoice_void",
    "quita la última factura": "invoice_void", "firma las facturas de hoy": "invoice_sign",
    "quiero que anules la última factura": "invoice_void", "¿puedes cancelar la factura F-2026-0002?": "invoice_void",
    "¿me puedes anular la última factura?": "invoice_void", "anúlame la última factura": "invoice_void",
    "anula esa factura": "invoice_void", "borra todas las facturas": "invoice_void",
    "elimina las facturas de este mes": "invoice_void", "cancela las facturas de hoy": "invoice_void",
    "haz una factura rectificativa de la última": "invoice_rectify", "corrige la última factura": "invoice_rectify",
    "modifica el importe de la factura 23": "invoice_rectify", "edita la factura F-1": "invoice_rectify",
    "cancela la factura de Juan Pérez": "invoice_void", "anula la factura del cliente Pepe": "invoice_void",
    "firma digitalmente la factura 12": "invoice_sign", "Rafael, anula la factura 23": "invoice_void",
    "dale de baja a la factura": "invoice_void", "da de baja la factura 23": "invoice_void",
    "invalida la factura 23": "invoice_void", "suprime la factura 23": "invoice_void",
    "tira la factura 23": "invoice_void", "deja sin efecto la factura 23": "invoice_void",
    "anula la factura que hice ayer": "invoice_void", "pon la factura 23 como anulada": "invoice_void",
    "marca la factura 23 como anulada": "invoice_void", "marca la factura 23 como firmada": "invoice_sign",
    "dime las facturas de hoy y anula la última": "invoice_void", "facturas de ayer, anula la 23": "invoice_void",
    "no, cancela la última factura": "invoice_void", "no sé, anula la factura 23": "invoice_void",
    "hay que anular la factura 23": "invoice_void", "anula la factura 23, no la 24": "invoice_void",
}
MSG_BY_REASON = {"invoice_void": MSG_INVOICE_VOID, "invoice_rectify": MSG_INVOICE_RECTIFY,
                 "invoice_sign": MSG_INVOICE_SIGN}
# Frases cercanas que NO son estas: intención que daba HEAD (bc4a16c) y que debe seguir igual.
COMO_EN_HEAD = {
    "factura de la luz": "unknown", "¿cuánto es la factura de la luz?": "unknown", "cancela la reserva": "unknown",
    "firma el contrato": "unknown", "anula el pedido": "unknown",
    "stock de mascarillas en el almacén de Mercadona": "get_inventory_status", "productos de limpieza": "unknown",
    "anula la factura de la luz": "unknown", "cancela la factura del gas": "unknown",
    "cancela la factura del proveedor": "unknown", "firma la factura del alquiler": "unknown",
    "borra la factura de la luz del mes pasado": "unknown", "¿cómo se anula una factura?": "unknown",
    "¿puedo anular una factura emitida?": "unknown", "explícame cómo rectificar una factura": "unknown",
    "¿qué es una factura rectificativa?": "unknown", "estoy agotado": "unknown",
    "se ha agotado la paciencia": "unknown", "me falta tiempo": "unknown", "¿qué me falta por hacer?": "unknown",
    "¿me falta algo para el lunes?": "unknown", "¿cuánto he facturado este mes?": "tpv_sales_summary",
    "facturación del mes": "tpv_sales_summary", "envía las facturas de ayer al gestor": "unknown",
    "descarga las facturas del mes pasado": "unknown", "facturas de la semana que viene": "unknown",
    "facturas de mañana": "unknown", "facturas de octubre": "unknown", "¿cuánto stock tengo?": "get_inventory_status",
    "stock bajo control": "get_inventory_status", "falta de stock en el mercado europeo": "get_inventory_status",
    "borra el stock de harina": "get_inventory_status", "cancela el envío": "unknown",
    "borra el cliente Juan": "unknown", "paga la factura de la luz": "unknown",
    "manda la factura al cliente": "unknown", "crea una factura para Juan": "unknown",
    "¿hay que reponer el papel del baño?": "unknown", "se agotaron las entradas del concierto": "unknown",
    "el producto está agotado en Amazon": "unknown", "nos falta personal": "unknown",
    "cambia la factura de la luz a mi nombre": "unknown", "facturas de hoy": "get_invoices_today",
    "¿cuál es mi última factura?": "get_last_invoice", "IVA del trimestre": "get_vat_quarter",
    "facturas pendientes de cobro": "get_pending_invoices", "firma el documento": "unknown",
    "rectifica el pedido": "unknown", "cancela mi plan": "unknown", "anula todo": "unknown",
}
LECTURAS = ("get_last_invoice", "get_invoices_today", "get_invoices_period", "get_vat_quarter",
            "get_inventory_status", "get_pending_invoices")


# ----------------------------------------------------------------------------- enrutado (reglas)
@pytest.mark.parametrize("msg,focus", STOCK.items())
def test_alertas_de_stock_son_la_lectura_con_su_foco(msg, focus):
    t = parse_intent(msg)
    assert t.intent == "get_inventory_status" and t.confidence >= 0.7 and not t.needs_clarification, (msg, t)
    assert t.metadata == {"focus": focus}, (msg, t.metadata)
    assert invoice_write_block(msg) is None


@pytest.mark.parametrize("msg,period", PERIODOS.items())
def test_facturas_por_periodo_son_la_lectura(msg, period):
    t = parse_intent(msg)
    assert t.intent == "get_invoices_period" and t.confidence >= 0.7 and not t.needs_clarification, (msg, t)
    assert t.metadata == {"period": period}
    assert invoice_write_block(msg) is None and legal_block(msg) is None


@pytest.mark.parametrize("msg,reason", ORDENES.items())
def test_ordenes_sobre_facturas_se_bloquean_y_nunca_son_lectura(msg, reason):
    blk = invoice_write_block(msg)
    assert blk is not None and blk[0] == reason and blk[1] == MSG_BY_REASON[reason], (msg, blk)
    assert parse_intent(msg).intent not in LECTURAS, msg


@pytest.mark.parametrize("msg,intent", COMO_EN_HEAD.items())
def test_frases_cercanas_quedan_como_en_head(msg, intent):
    t = parse_intent(msg)
    assert t.intent == intent, (msg, t.intent)
    assert "focus" not in t.metadata and "period" not in t.metadata
    assert invoice_write_block(msg) is None, msg


def test_bloqueos_previos_no_cambian():
    assert legal_block("envía la factura a Hacienda")[0] == "aeat_submission"
    assert legal_block("presenta el IVA")[0] == "tax_filing"
    assert invoice_write_block("envía la factura a Hacienda") is None
    assert schedule_write_block("borra el cuadrante") is not None and invoice_write_block("borra el cuadrante") is None


def test_negacion_no_se_ejecuta():
    t = parse_intent("no me enseñes los productos sin stock")
    assert t.intent == "get_inventory_status" and t.needs_clarification  # se pregunta, no se lee
    t = parse_intent("no me enseñes las facturas de ayer")
    assert t.intent != "get_invoices_period" or t.needs_clarification


# ----------------------------------------------------------------------------- textos y fechas
def test_periodos_resueltos_en_servidor():
    sab = date(2026, 10, 24)  # sábado
    assert invoice_period_bounds("yesterday", sab) == (date(2026, 10, 23), date(2026, 10, 23))
    assert invoice_period_bounds("week", sab) == (date(2026, 10, 19), sab)
    assert invoice_period_bounds("last_week", sab) == (date(2026, 10, 12), date(2026, 10, 18))
    assert invoice_period_bounds("month", sab) == (date(2026, 10, 1), sab)
    assert invoice_period_bounds("last_month", sab) == (date(2026, 9, 1), date(2026, 9, 30))
    assert invoice_period_bounds("last_month", date(2026, 1, 5)) == (date(2025, 12, 1), date(2025, 12, 31))
    assert invoice_period_bounds("week", date(2026, 10, 19)) == (date(2026, 10, 19), date(2026, 10, 19))
    with pytest.raises(ValueError):
        invoice_period_bounds("trimestre", sab)


def _inv_data(**kw):
    base = {"total_skus": 0, "tracked_skus": 0, "untracked_skus": 0, "out_of_stock_count": 0, "low_stock_count": 0,
            "without_min_count": 0, "total_units": 0, "out_of_stock_items": [], "low_stock_items": [],
            "top_items": []}
    base.update(kw)
    return base


def test_textos_honestos_sin_control_y_sin_minimos():
    assert inventory_alerts_text(_inv_data(), "low").startswith("No tienes productos dados de alta")
    sin_control = _inv_data(total_skus=4, untracked_skus=4)
    assert inventory_alerts_text(sin_control, "out") == (
        "Inventario: 4 referencias, pero ninguna lleva control de stock (no tienen stock indicado en el TPV ni en "
        "el inventario), así que no puedo saber qué se ha agotado ni qué está bajo mínimos.")
    sin_minimos = _inv_data(total_skus=2, tracked_skus=2, without_min_count=2, total_units=5,
                            top_items=[{"name": "Cerveza", "stock": 5.0}],
                            out_of_stock_count=1, out_of_stock_items=[{"name": "Tarta", "stock": 0.0}])
    low = inventory_alerts_text(sin_minimos, "low")
    assert low.startswith("No puedo saber qué está bajo mínimos porque ningún producto tiene mínimo definido.")
    assert "ninguno de los" not in low.lower() and "Además, sin stock: 1 (Tarta (0))." in low
    general = inventory_status_text(sin_minimos)
    assert "Ninguna bajo mínimos" not in general
    assert "No puedo saber cuáles están bajo mínimos porque ninguna tiene mínimo definido." in general
    con_minimo = _inv_data(total_skus=2, tracked_skus=2, without_min_count=0, total_units=9,
                           top_items=[{"name": "Cerveza", "stock": 5.0}])
    assert inventory_alerts_text(con_minimo, "low") == (
        "Ninguno de los 2 productos con mínimo definido está bajo mínimos.")
    assert "Ninguna bajo mínimos (de las 2 con mínimo definido)." in inventory_status_text(con_minimo)
    with pytest.raises(ValueError):
        inventory_alerts_text(con_minimo, "todo")


# ----------------------------------------------------------------------------- datos sembrados
def _stock_empresas(db):
    """A (sesión): Cerveza 40, Tarta de queso 0, Vino tinto 3 (ERP «Vino tinto » con mínimo 5), Menú sin control.
    B (2ª empresa del mismo usuario): Croquetas 0. T (otro tenant): Patatas 0 y Aceite 1 con mínimo 10."""
    u, a = _user(db)
    b = _segunda_empresa(db, u)
    t, c = _user(db)
    _tpv(db, u, a, "Cerveza", 40)
    _tpv(db, u, a, "Tarta de queso", 0)
    _tpv(db, u, a, "Vino tinto", 3)
    _erp(db, a, "Vino tinto ", 3, 5)  # nombre con espacio final (ERP): sale recortado y es la misma referencia
    _tpv(db, u, a, "Menú del día", None)
    _tpv(db, u, b, "Croquetas", 0)
    _tpv(db, t, c, "Patatas", 0)
    _erp(db, c, "Aceite", 1, 10)
    return u, a


def _say(client, headers, path, msg, thread=None):
    r = client.post(f"{P}{path}", headers=headers,
                    json={"message": msg, "thread_id": thread or f"t-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200, r.text
    return r.json()


def _ajenos_stock_fuera(msg):
    for otro in ("Croquetas", "Patatas", "Aceite"):
        assert otro not in msg, (otro, msg)


ESPERADO_STOCK = {
    "productos sin stock": (
        "Sin stock: 1 (Tarta de queso (0)). 1 producto no lleva control de stock: de ese no sé cuántas unidades "
        "quedan."),
    "¿algo bajo mínimos?": (
        "Bajo mínimos: 1 (Vino tinto (3, mínimo 5)). 2 con control de stock no tienen mínimo definido. Además, sin "
        "stock: 1 (Tarta de queso (0)). 1 producto no lleva control de stock: de ese no sé cuántas unidades quedan."),
    "¿qué me falta?": (
        "Sin stock: 1 (Tarta de queso (0)). Bajo mínimos: 1 (Vino tinto (3, mínimo 5)). 2 con control de stock no "
        "tienen mínimo definido. 1 producto no lleva control de stock: de ese no sé cuántas unidades quedan."),
}


# ----------------------------------------------------------------------------- stock: chat con login real
def test_stock_real_por_chat_de_afrodita_y_jarvis_y_aislado(db, client):
    u, a = _stock_empresas(db)
    inv = company_inventory_status(db, a.id)
    assert sorted(i["name"] for i in inv["items"]) == ["Cerveza", "Menú del día", "Tarta de queso", "Vino tinto"]
    h = _login(client, u)
    for msg, esperado in ESPERADO_STOCK.items():
        for path in ("/chat/afrodita/chat", "/jarvis/message"):
            out = _say(client, h, path, msg)
            assert out["message"] == esperado, (path, msg, out["message"])
            _ajenos_stock_fuera(out["message"])
    for msg in ("productos con poco stock", "¿qué se ha agotado?", "qué productos no tienen stock"):
        out = _say(client, h, "/chat/afrodita/chat", msg)
        assert "Tarta de queso (0)" in out["message"], (msg, out["message"])
        _ajenos_stock_fuera(out["message"])
    assert not approvals(db, u)
    assert rows(db, a.id, action="get_inventory_status")  # registro real de la lectura


def test_stock_sin_minimos_lo_dice_y_no_inventa(db, client):
    u, a = _user(db)
    _tpv(db, u, a, "Café", 30)
    _tpv(db, u, a, "Tostada", 0)
    h = _login(client, u)
    out = _say(client, h, "/jarvis/message", "¿algo bajo mínimos?")
    assert out["message"] == ("No puedo saber qué está bajo mínimos porque ningún producto tiene mínimo definido. "
                              "Además, sin stock: 1 (Tostada (0)).")
    out = _say(client, h, "/chat/afrodita/chat", "¿cómo está el inventario?")
    assert "Ninguna bajo mínimos" not in out["message"]
    assert "No puedo saber cuáles están bajo mínimos porque ninguna tiene mínimo definido." in out["message"]


def test_ejecutor_rechaza_un_foco_invalido(db):
    u, a = _user(db)
    r = asyncio.run(execute_agent_action(db, user=u, agent="AFRODITA", action="get_inventory_status",
                                         payload={"focus": "todo"}))
    assert not r.get("executed") and r.get("status") == "invalid_payload", r
    r = asyncio.run(execute_agent_action(db, user=u, agent="RAFAEL", action="get_invoices_period",
                                         payload={"period": "siglo"}))
    assert not r.get("executed") and r.get("status") == "invalid_payload", r


# ----------------------------------------------------------------------------- facturas: chat con login real
def _local_noon_naive(day):
    start, _ = day_bounds_utc(day)
    return (start + timedelta(hours=12)).replace(tzinfo=None)


def _facturas_empresas(db):
    """A (sesión): ayer 121,00 y 60,50 emitidas + borrador + anulada; hoy 10,00; día 1 del mes pasado 200,00.
    B (2ª empresa del mismo usuario) y T (otro tenant): una factura ayer cada una."""
    hoy = today_local()
    ayer = hoy - timedelta(days=1)
    mes_pasado = (hoy.replace(day=1) - timedelta(days=1)).replace(day=1)
    u, a = _user(db)
    b = _segunda_empresa(db, u)
    t, c = _user(db)
    sembradas = [
        (_inv(db, a.id, 121.0, when=_local_noon_naive(ayer)), ayer),
        (_inv(db, a.id, 60.5, when=_local_noon_naive(ayer)), ayer),
        (_inv(db, a.id, 33.0, status=InvoiceStatus.DRAFT, when=_local_noon_naive(ayer)), ayer),
        (_inv(db, a.id, 44.0, status=InvoiceStatus.VOID, when=_local_noon_naive(ayer)), ayer),
        (_inv(db, a.id, 10.0, when=_local_noon_naive(hoy)), hoy),
        (_inv(db, a.id, 200.0, when=_local_noon_naive(mes_pasado)), mes_pasado),
    ]
    ajenas = [_inv(db, b.id, 999.0, when=_local_noon_naive(ayer)), _inv(db, c.id, 777.0, when=_local_noon_naive(ayer))]
    return u, a, sembradas, ajenas


def _esperado(sembradas, period):
    first, last = invoice_period_bounds(period, today_local())
    dentro = [i for i, d in sembradas if first <= d <= last]
    emitidas = [i for i in dentro if i.status not in (InvoiceStatus.DRAFT, InvoiceStatus.VOID)]
    return dentro, emitidas


@pytest.mark.parametrize("msg,period", [("facturas de ayer", "yesterday"), ("facturas de este mes", "month"),
                                        ("facturas del mes pasado", "last_month"),
                                        ("facturas de la semana", "week"),
                                        ("facturas de la semana pasada", "last_week")])
def test_facturas_por_periodo_por_chat_de_rafael_y_jarvis_y_aisladas(db, client, msg, period):
    u, a, sembradas, ajenas = _facturas_empresas(db)
    h = _login(client, u)
    dentro, emitidas = _esperado(sembradas, period)
    for path in ("/chat/rafael/chat", "/jarvis/message"):
        m = _say(client, h, path, msg)["message"]
        if emitidas:
            total = sum(float(i.total) for i in emitidas)
            assert f": {len(emitidas)} por {_eur(total)} " in m, (path, msg, m)
            for i in emitidas:
                assert i.invoice_number in m, (i.invoice_number, m)
        else:
            assert "no hay facturas emitidas en tu empresa: 0 facturas." in m, (path, msg, m)
        borradores = sum(1 for i in dentro if i.status == InvoiceStatus.DRAFT)
        assert (f"{borradores} borrador(es) sin emitir" in m) == bool(borradores), m
        for i in ajenas:
            assert i.invoice_number not in m and "999,00 €" not in m and "777,00 €" not in m, m
    assert rows(db, a.id, action="get_invoices_period")


def test_facturas_de_ayer_texto_literal(db, client):
    u, a, sembradas, _ = _facturas_empresas(db)
    ayer = today_local() - timedelta(days=1)
    f1, f2 = sembradas[0][0], sembradas[1][0]  # mismo instante: manda el id mayor (f2) primero
    m = _say(client, _login(client, u), "/chat/rafael/chat", "facturas de ayer")["message"]
    assert m == (f"Facturas de ayer ({ayer:%d/%m/%Y}): 2 por 181,50 € (IVA 31,50 €): {f2.invoice_number} (60,50 €), "
                 f"{f1.invoice_number} (121,00 €). Además: 1 borrador(es) sin emitir, 1 anulada(s)."), m


# ----------------------------------------------------------------------------- órdenes: bloqueo real
def test_ordenes_sobre_facturas_respuesta_fija_sin_llm_y_sin_tocar_nada(db, client):
    u, a, sembradas, _ = _facturas_empresas(db)
    h = _login(client, u)
    antes = {i.id: i.status for i, _ in sembradas}
    for msg, reason in ORDENES.items():
        for path in ("/jarvis/message", "/chat/rafael/chat"):
            out = _say(client, h, path, msg)
            assert out["success"] is False and out["status"] == "not_available", (path, msg, out)
            assert out["message"] == MSG_BY_REASON[reason], (path, msg, out["message"])
            assert not out.get("executed_action") and not out.get("needs_confirmation")
    db.expire_all()
    assert {i.id: i.status for i in db.query(Invoice).filter(Invoice.company_id == a.id)} == antes
    assert not approvals(db, u)
    assert rows(db, a.id, action="invoice_write_block")


NEGADAS = ["no canceles la factura", "no anules la última factura", "nunca firmes la factura",
           "no quiero que anules la factura 23", "no me anules la factura 23",
           "para, no canceles la factura", "no borres la factura F-2026-0001", "no rectifiques la factura"]


@pytest.mark.parametrize("msg", NEGADAS)
def test_orden_negada_se_reconoce_y_no_es_bloqueo(msg):
    assert invoice_write_block(msg) is None and negated_invoice_order(msg), msg


@pytest.mark.parametrize("msg", ["no me enseñes la última factura", "no hay stock de harina", "no sé qué factura es",
                                 "¿no puedo anular una factura?", "no quiero la factura de la luz"])
def test_otras_negaciones_no_son_orden_negada(msg):
    assert not negated_invoice_order(msg), msg


@pytest.mark.parametrize("msg", NEGADAS[:4])
def test_negacion_y_parada_no_ejecutan_ni_bloquean(db, client, msg):
    u, a, sembradas, _ = _facturas_empresas(db)
    h = _login(client, u)
    for path in ("/jarvis/message", "/chat/rafael/chat"):
        out = _say(client, h, path, msg)
        assert out["message"] == MSG_INVOICE_NEGATED, (path, out)
        assert not out.get("executed_action") and not out.get("needs_confirmation")
    db.expire_all()
    assert db.query(Invoice).filter(Invoice.company_id == a.id, Invoice.status == InvoiceStatus.VOID).count() == 1
    assert not approvals(db, u)


def test_sin_credenciales_rechazo_controlado(client):
    for path in ("/chat/rafael/chat", "/chat/afrodita/chat", "/jarvis/message"):
        r = client.post(f"{P}{path}", json={"message": "facturas de ayer", "thread_id": "t-x"})
        assert r.status_code in (401, 403), (path, r.text)


# ============================================================================= revisión 2
# Criterio facturas frente a ventas: el SUSTANTIVO «factura(s)» = documentos de factura (RAFAEL); el VERBO
# «facturar» («¿cuánto he facturado este mes?», «¿cuánto facturé ayer?») = importe vendido (ventas TPV / cierre),
# como ya hacía HEAD con «he facturado» y «facturamos».
@pytest.mark.parametrize("msg,intent,meta", [
    ("¿cuánto facturé ayer?", "get_daily_close", {"day": "yesterday"}),
    ("¿qué facturé ayer?", "get_daily_close", {"day": "yesterday"}),
    ("¿cuánto he facturado ayer?", "get_daily_close", {"day": "yesterday"}),  # como HEAD
    ("¿cuánto he facturado este mes?", "tpv_sales_summary", {"days": 30}),  # como HEAD
    ("inventario", "get_inventory_status", {}), ("stock", "get_inventory_status", {}),
])
def test_verbo_facturar_es_venta_e_inventario_a_secas(msg, intent, meta):
    t = parse_intent(msg)
    assert t.intent == intent and t.confidence >= 0.7 and not t.needs_clarification, (msg, t)
    assert t.metadata == meta


INV = ["Cerveza", "Vino tinto", "Tarta de queso", "Menú del día", "Coca-Cola", "M&M's", "7-Up"]


# (a) producto del inventario de la empresa de la sesión -> lectura, en cualquier chat
@pytest.mark.parametrize("msg,prod", [
    ("¿me queda cerveza?", "cerveza"), ("¿nos quedan cervezas?", "cervezas"),
    ("¿cuántas cervezas me quedan?", "cervezas"), ("¿me queda vino?", "vino"),
    ("¿me queda algo de cerveza?", "cerveza"), ("¿queda vino?", "vino"),
    ("¿me queda tarta de queso?", "tarta de queso"), ("¿me queda Coca-Cola?", "coca-cola"),
    ("¿me quedan M&M's?", "m&m's"), ("¿me queda 7-Up?", "7-up"),
])
def test_me_queda_producto_de_la_sesion_es_lectura(msg, prod):
    t = product_stock_task(msg, INV)
    assert t is not None and t.intent == "get_inventory_status", msg
    assert t.metadata == {"focus": "product", "product": prod}


# (b) el stock nombrado de forma explícita -> lectura aunque X no esté («No encuentro…»), en cualquier chat
@pytest.mark.parametrize("msg,prod", [
    ("¿cuánto stock queda de harina?", "harina"), ("¿hay stock de croquetas?", "croquetas"),
    ("stock de leche", "leche"), ("¿cuántas unidades quedan de leche?", "leche"), ("existencias de leche", "leche"),
    ("¿hay stock de patatas?", "patatas"),
])
def test_stock_explicito_de_x_es_lectura_aunque_no_exista(msg, prod):
    t = product_stock_task(msg, [])
    assert t is not None and t.metadata == {"focus": "product", "product": prod}, msg


# (c) «¿me queda X?» sin palabra de stock y X fuera del inventario de la sesión: solo AFRODITA responde
@pytest.mark.parametrize("msg", ["¿me queda leche?", "¿me quedan patatas?", "¿nos queda vino blanco?"])
def test_me_queda_x_que_no_esta_solo_en_afrodita(msg):
    assert product_stock_task(msg, INV) is None, msg
    t = product_stock_task(msg, INV, domain=True)
    assert t is not None and t.metadata["focus"] == "product", msg


# (d) filtro previo: no son productos ni en AFRODITA; quedan como en HEAD
@pytest.mark.parametrize("msg,intent", [
    ("¿me queda margen?", "get_metrics"), ("¿me queda saldo?", "get_cashflow"),
    ("¿cuántos euros me quedan?", "unknown"), ("¿me queda alguna duda?", "unknown"),
    ("¿me queda el pantalón?", "unknown"), ("¿me quedan licencias?", "unknown"),
    ("¿me quedan créditos?", "unknown"), ("¿me quedan tokens?", "unknown"), ("¿cuántas sesiones me quedan?", "unknown"),
    ("¿me queda gasolina?", "unknown"), ("¿me queda cobertura?", "unknown"), ("¿me queda pendiente algo?", "unknown"),
])
def test_filtro_previo_no_son_productos(msg, intent):
    assert product_stock_task(msg, INV, domain=True) is None, msg
    assert parse_intent(msg).intent == intent, msg


def test_stock_de_la_competencia_queda_como_en_head():
    assert product_stock_task("el stock de la competencia", [], domain=True) is None
    t = parse_intent("el stock de la competencia")
    assert t.intent == "get_inventory_status" and t.confidence < 0.7 and t.metadata == {}


# No son productos (criterio determinista `_NOT_PRODUCT`): quedan como en HEAD (intención de HEAD)
@pytest.mark.parametrize("msg,intent", [
    ("¿me queda tiempo?", "unknown"), ("¿cuánto me queda por pagar?", "unknown"), ("no me queda paciencia", "unknown"),
    ("me queda poco", "unknown"), ("¿cuánto me queda?", "unknown"), ("¿me queda bien?", "unknown"),
    ("¿me queda batería?", "unknown"), ("¿me queda saldo?", "get_cashflow"), ("¿me queda bien esta camisa?", "unknown"),
    ("¿nos queda mucho?", "unknown"), ("¿me queda algo?", "unknown"), ("¿cuánto me queda de vacaciones?", "unknown"),
    ("¿me quedan días de vacaciones?", "unknown"), ("¿me queda dinero?", "unknown"),
    ("¿me queda realmente algo?", "unknown"),
])
def test_me_queda_sin_producto_sigue_como_en_head(msg, intent):
    assert product_stock_task(msg, INV, domain=True) is None, msg
    t = parse_intent(msg)
    assert t.intent == intent and t.metadata.get("focus") is None, (msg, t.intent)


@pytest.mark.parametrize("msg,intent", [
    ("¿qué es el inventario?", "get_inventory_status"), ("¿qué es el stock?", "get_inventory_status"),
    ("¿qué significa stock?", "get_inventory_status"), ("¿para qué sirve el inventario?", "get_inventory_status"),
    ("¿cómo funciona el inventario?", "get_inventory_status"), ("¿cómo se hace el inventario?", "get_inventory_status"),
])
def test_preguntas_de_concepto_quedan_como_en_head(msg, intent):
    t = parse_intent(msg)
    # como HEAD: baja confianza (0,68) y sin foco -> no se vuelca el inventario
    assert t.intent == intent and t.confidence < 0.7 and t.metadata == {}, (msg, t.confidence, t.metadata)


NO_FACTURA_CON_CONTEXTO = ["cancela la última cita", "anula la última reserva", "quita 10 euros del total",
                           "cambia 2024 por 2025", "borra la 3", "elimina la anterior", "quita la última",
                           "borra la de ayer", "cancela la de mañana", "borra el último mensaje",
                           "anula la reserva de ayer", "suprime el último párrafo"]


@pytest.mark.parametrize("msg", ["anúlame la última", "anula la última", "anula la nº 23", "cancélala", "bórrala",
                                 "anula la de ayer", "firma la última", "anula la número 23", "anula la F-23",
                                 "anula la 23", "anula la última por favor", "borra la nº 23",
                                 "quita la F-2026-0001, gracias", "anula la que hice ayer"])
def test_ordenes_sin_la_palabra_factura_solo_con_contexto(msg):
    assert invoice_order_check(msg, invoice_context=False) is None, msg
    chk = invoice_order_check(msg, invoice_context=True)
    assert chk is not None and chk[0] == "block", (msg, chk)


@pytest.mark.parametrize("msg", ["cancela", "anula", "firma", "cancela eso", "borra todo", "cancela la cita",
                                 "anula la reserva 3", "tira la basura", "da de baja al empleado Luis",
                                 "marca la reserva como anulada", "marca la última factura como cobrada"]
                         + NO_FACTURA_CON_CONTEXTO)
def test_sin_objeto_de_factura_no_se_bloquea_ni_con_contexto(msg):
    assert invoice_order_check(msg, invoice_context=True) is None, msg


@pytest.mark.parametrize("msg", ["¿hay que firmar las facturas?", "¿se puede cancelar una factura?",
                                 "¿cómo se firma una factura?", "¿tengo que firmar la factura?",
                                 "¿hay que anular la factura 23?"])
def test_preguntas_hay_que_no_son_ordenes(msg):
    assert invoice_order_check(msg) is None, msg


def test_muletillas_no_niegan_la_orden():
    for msg in ("no, cancela la última factura", "no sé, anula la factura 23", "bueno, firma la factura"):
        chk = invoice_order_check(msg)
        assert chk is not None and chk[0] == "block", (msg, chk)
        assert not negated_invoice_order(msg), msg


# ----------------------------------------------------------------------------- lecturas de otro agente
def test_stock_en_el_chat_de_rafael_es_la_lectura_real_de_afrodita(db, client):
    u, a = _stock_empresas(db)
    h = _login(client, u)
    for msg, esperado in ESPERADO_STOCK.items():
        out = _say(client, h, "/chat/rafael/chat", msg)
        assert out["message"] == f"Esto lo lleva AFRODITA: {esperado}", (msg, out["message"])
    out = _say(client, h, "/chat/rafael/chat", "inventario")
    assert out["message"].startswith("Esto lo lleva AFRODITA: Inventario: 4 referencias"), out["message"]
    _ajenos_stock_fuera(out["message"])
    assert rows(db, a.id, action="get_inventory_status")


def test_facturas_en_el_chat_de_afrodita_son_la_lectura_real_de_rafael(db, client):
    u, a, sembradas, ajenas = _facturas_empresas(db)
    h = _login(client, u)
    hoy = today_local()
    m = _say(client, h, "/chat/afrodita/chat", "facturas de ayer")["message"]
    assert m.startswith(f"Esto lo lleva RAFAEL: Facturas de ayer ({hoy - timedelta(days=1):%d/%m/%Y}): 2 por "
                        "181,50 €"), m
    m = _say(client, h, "/chat/afrodita/chat", "facturas de hoy")["message"]
    assert m.startswith(f"Esto lo lleva RAFAEL: Facturas de hoy ({hoy:%d/%m/%Y}): 1 por 10,00 €"), m
    m = _say(client, h, "/chat/afrodita/chat", "facturas del mes")["message"]
    assert m.startswith("Esto lo lleva RAFAEL: Facturas de este mes ("), m
    for i in ajenas:
        assert i.invoice_number not in m


def test_lectura_de_otro_agente_pasa_por_el_modulo_de_la_empresa(db, client, monkeypatch):
    from services import module_gate

    original = module_gate.check_action

    def _sin_tpv(db_, user_, action_type):
        if action_type == "get_daily_close":
            return {"module": "tpv", "message": "Tu empresa no tiene activo el módulo TPV."}
        return original(db_, user_, action_type)

    monkeypatch.setattr(module_gate, "check_action", _sin_tpv)
    u, a, *_ = _facturas_empresas(db)
    out = _say(client, _login(client, u), "/chat/afrodita/chat", "cierre de ayer")
    assert out["message"] == "Esto lo lleva RAFAEL: Tu empresa no tiene activo el módulo TPV.", out
    assert not out.get("executed_action")


def test_facturas_de_hoy_en_formato_es(db, client):
    u, a, *_ = _facturas_empresas(db)
    m = _say(client, _login(client, u), "/chat/rafael/chat", "facturas de hoy")["message"]
    assert f"Facturas de hoy ({today_local():%d/%m/%Y}): 1 por 10,00 €" in m, m


# ----------------------------------------------------------------------------- «¿me queda X?» con datos reales
def test_me_queda_x_con_el_inventario_real_y_aislado(db, client):
    u, a = _stock_empresas(db)
    h = _login(client, u)
    casos = {
        "¿me queda cerveza?": "Cerveza: quedan 40 unidades.",
        "¿me queda vino?": "Vino tinto: quedan 3 unidades (mínimo 5: bajo mínimos).",
        "¿me queda tarta de queso?": "Tarta de queso: sin stock (0 unidades).",
        "¿me queda menú del día?": "Menú del día no lleva control de stock, así que no sé cuántas unidades quedan.",
        "¿cuánto stock queda de harina?": "No encuentro «harina» en tu inventario.",
        # producto de la 2ª empresa del mismo usuario y de otro tenant: no están en la empresa de la sesión
        "¿hay stock de croquetas?": "No encuentro «croquetas» en tu inventario.",
        "¿cuánto stock queda de patatas?": "No encuentro «patatas» en tu inventario.",
    }
    for msg, esperado in casos.items():
        for path in ("/chat/afrodita/chat", "/jarvis/message"):
            out = _say(client, h, path, msg)
            assert out["message"] == esperado, (path, msg, out["message"])
        out = _say(client, h, "/chat/rafael/chat", msg)
        assert out["message"] == f"Esto lo lleva AFRODITA: {esperado}", (msg, out["message"])
    r = asyncio.run(execute_agent_action(db, user=u, agent="AFRODITA", action="get_inventory_status",
                                         payload={"focus": "product", "product": ""}))
    assert not r.get("executed") and r.get("status") == "invalid_payload", r


# ----------------------------------------------------------------------------- órdenes con contexto
def test_rafael_entiende_la_ultima_sin_la_palabra_factura(db, client):
    u, a, sembradas, _ = _facturas_empresas(db)
    h = _login(client, u)
    for msg in ("anula la última", "cancélala", "anula la nº 23"):
        out = _say(client, h, "/chat/rafael/chat", msg)
        assert out["status"] == "not_available" and out["message"] == MSG_INVOICE_VOID, (msg, out)
    db.expire_all()
    assert db.query(Invoice).filter(Invoice.company_id == a.id, Invoice.status == InvoiceStatus.VOID).count() == 1


def test_zeus_usa_el_turno_anterior_de_facturas_del_mismo_hilo(db, client):
    u, a, *_ = _facturas_empresas(db)
    h = _login(client, u)
    hilo = f"t-{uuid.uuid4().hex[:8]}"
    assert _say(client, h, "/jarvis/message", "facturas de ayer", thread=hilo)["message"].startswith("Facturas de ayer")
    out = _say(client, h, "/jarvis/message", "anula la última", thread=hilo)
    assert out["status"] == "not_available" and out["message"] == MSG_INVOICE_VOID, out
    out = _say(client, h, "/jarvis/message", "dime las facturas de hoy y anula la última")
    assert out["status"] == "not_available" and out["message"] == MSG_INVOICE_VOID, out
    assert not approvals(db, u)


def test_negacion_con_clitico_y_contexto():
    assert negated_invoice_order("no me la anules", invoice_context=True)
    assert not negated_invoice_order("no me la anules", invoice_context=False)


def test_frases_que_no_son_facturas_no_se_bloquean_en_rafael_ni_en_zeus_con_contexto(db, client, monkeypatch):
    """Estas frases no son de facturas: siguen su camino de HEAD (el modelo conversacional), que aqui es un stub
    explicito; lo que se comprueba es que NO reciben el bloqueo de facturas ni tocan nada."""
    import services.unified_agent_runtime as rt

    monkeypatch.setattr(rt, "run_chat", lambda *a, **k: {"success": True, "message": "respuesta-llm-stub"})
    u, a, sembradas, _ = _facturas_empresas(db)
    h = _login(client, u)
    hilo = f"t-{uuid.uuid4().hex[:8]}"
    assert _say(client, h, "/jarvis/message", "facturas de ayer", thread=hilo)["message"].startswith("Facturas de ayer")
    for msg in NO_FACTURA_CON_CONTEXTO:
        assert invoice_order_check(msg, invoice_context=True) is None, msg
        for path, th in (("/chat/rafael/chat", None), ("/jarvis/message", hilo)):
            out = _say(client, h, path, msg, thread=th)
            assert out.get("message") not in (MSG_INVOICE_VOID, MSG_INVOICE_RECTIFY, MSG_INVOICE_SIGN), (path, msg)
    db.expire_all()
    assert db.query(Invoice).filter(Invoice.company_id == a.id, Invoice.status == InvoiceStatus.VOID).count() == 1


def test_me_queda_x_de_otra_empresa_u_otro_tenant_no_filtra_nada(db, client, monkeypatch):
    """La leche de la 2ª empresa del mismo usuario y las patatas de otro tenant siguen exactamente el mismo camino
    que un producto que no existe en ninguna empresa (no se revela a quién pertenece)."""
    import services.unified_agent_runtime as rt

    llm = []
    monkeypatch.setattr(rt, "run_chat", lambda *a, **k: llm.append(1) or {"success": True,
                                                                         "message": "respuesta-llm-stub"})
    u, a = _user(db)
    b = _segunda_empresa(db, u)
    t, c = _user(db)
    _tpv(db, u, a, "Cerveza", 40)
    _tpv(db, u, a, "Coca-Cola", 24)
    _tpv(db, u, b, "Leche", 12)
    _tpv(db, t, c, "Patatas", 7)
    h = _login(client, u)
    for path in ("/chat/afrodita/chat", "/jarvis/message", "/chat/rafael/chat"):
        pre = "Esto lo lleva AFRODITA: " if path == "/chat/rafael/chat" else ""
        # (a) productos de la sesión: stock real, sin LLM
        n = len(llm)
        assert _say(client, h, path, "¿me queda cerveza?")["message"] == f"{pre}Cerveza: quedan 40 unidades."
        assert _say(client, h, path, "¿me queda Coca-Cola?")["message"] == f"{pre}Coca-Cola: quedan 24 unidades."
        # (b) stock explícito de X que no está en la sesión (otra empresa, otro tenant, ninguna): igual, sin LLM
        for prod in ("leche", "patatas", "unicornios"):
            out = _say(client, h, path, f"¿hay stock de {prod}?")
            assert out["message"] == f"{pre}No encuentro «{prod}» en tu inventario.", (path, out["message"])
        assert len(llm) == n, path
        # (c) «¿me queda X?» sin palabra de stock y X fuera de la sesión
        for prod in ("leche", "patatas", "unicornios"):
            out = _say(client, h, path, f"¿me queda {prod}?")
            if path == "/chat/afrodita/chat":
                assert out["message"] == f"No encuentro «{prod}» en tu inventario.", out["message"]
            else:  # ZEUS/JARVIS y RAFAEL: como en HEAD (no es una lectura de inventario)
                assert "No encuentro" not in out["message"] and "Leche" not in out["message"], (path, out)
                assert not out.get("executed_action"), (path, out)
