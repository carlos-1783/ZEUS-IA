"""AFRODITA · inventario del chat sobre el catálogo REAL de la empresa (productos del TPV + ERP).

Antes la consulta leía solo la tabla ERP `products` y a un restaurante (catálogo en `tpv_products`)
le decía «0 referencias». Ahora: stock real del TPV de la empresa de la sesión, ERP sin duplicar,
productos sin control de stock (stock NULL) dichos como tales, y el vacío honesto. Lectura por el
ejecutor, por el chat JARVIS y por los endpoints HTTP del agente con login real (token Bearer).
Sin red ni LLM (run_chat es un stub que delata si se le llamó).
"""

from __future__ import annotations

import asyncio
import uuid

from app.models.erp import Product, TPVProduct
from services.afrodita_ops_service_v1 import company_inventory_status
from services.zeus_agent_executor_v1 import execute_agent_action

from test_fase2_step1_chat_e2e_v1 import LLM_STUB
from test_jarvis_acciones_ops_v1 import _env, _user, approvals, client, db, say  # noqa: F401

P = "/api/v1"


def _tpv(db, user, company, name, stock):
    p = TPVProduct(user_id=user.id, company_id=company.id, product_id=f"PROD_T_{uuid.uuid4().hex[:10]}",
                   name=name, category="Bebidas", price=1.5, price_with_iva=1.65, iva_rate=10.0, stock=stock)
    db.add(p)
    db.commit()
    return p


def _erp(db, company, name, qty, threshold, track=True):
    p = Product(sku=f"INV-{uuid.uuid4().hex[:8]}", name=name, price=1.0, company_id=company.id,
                track_inventory=track, quantity_on_hand=qty, low_stock_threshold=threshold)
    db.add(p)
    db.commit()
    return p


def _restaurante_a(db):
    """Empresa A: con stock, sin stock, bajo mínimos (gemelo ERP con mínimo) y sin control de stock."""
    u, c = _user(db)
    _tpv(db, u, c, "Cerveza", 40)
    _tpv(db, u, c, "Tarta de queso", 0)
    _tpv(db, u, c, "Vino tinto", 3)
    _erp(db, c, "Vino tinto", 3, 5)  # mismo producto en el ERP: una sola referencia, mínimo 5
    _tpv(db, u, c, "Menú del día", None)
    return u, c


def _restaurante_b(db):
    u, c = _user(db)
    _tpv(db, u, c, "Croquetas", 12)
    return u, c


def _login(client, user):
    r = client.post(f"{P}/auth/login", data={"username": user.email, "password": "TestPass1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ----------------------------------------------------------------------------- lectura (servicio)
def test_stock_real_del_tpv_de_su_empresa_sin_duplicar(db):
    ua, ca = _restaurante_a(db)
    _restaurante_b(db)
    inv = company_inventory_status(db, ca.id)
    names = sorted(i["name"] for i in inv["items"])
    assert names == ["Cerveza", "Menú del día", "Tarta de queso", "Vino tinto"]  # sin Croquetas (empresa B)
    assert inv["total_skus"] == 4 and inv["tpv_products"] == 4 and inv["erp_products"] == 1
    assert inv["tracked_skus"] == 3 and inv["untracked_skus"] == 1
    assert inv["total_units"] == 43
    assert [i["name"] for i in inv["out_of_stock_items"]] == ["Tarta de queso"]
    assert inv["low_stock_count"] == 1
    low = inv["low_stock_items"][0]
    assert low["name"] == "Vino tinto" and low["stock"] == 3 and low["min_stock"] == 5
    assert inv["top_items"][0] == {"name": "Cerveza", "stock": 40.0}
    assert [i["name"] for i in inv["untracked_items"]] == ["Menú del día"]


def test_empresa_vacia_y_productos_sin_control_de_stock(db):
    _, vacia = _user(db)
    inv = company_inventory_status(db, vacia.id)
    assert inv["total_skus"] == 0 and inv["items"] == []
    u, c = _user(db)
    for n in ("Café", "Caña", "Tostada", "Menú"):  # como el alta: 4 productos TPV con stock NULL
        _tpv(db, u, c, n, None)
    inv = company_inventory_status(db, c.id)
    assert inv["total_skus"] == 4 and inv["tracked_skus"] == 0 and inv["out_of_stock_count"] == 0


# ----------------------------------------------------------------------------- ejecutor y chat
def test_ejecutor_y_chat_dan_el_stock_real_de_su_empresa(db, client):
    ua, ca = _restaurante_a(db)
    ub, cb = _restaurante_b(db)
    r = asyncio.run(execute_agent_action(db, user=ua, agent="AFRODITA", action="get_inventory_status", payload={}))
    assert r["success"] and r["executed"] and r["company_id"] == ca.id
    assert "Croquetas" not in r["message"]
    oa = say(client, ua, "¿qué stock tengo?")
    msg = oa["message"]
    assert "4 referencias (3 con control de stock y 1 sin control de stock)" in msg
    assert "43 unidades en stock" in msg
    assert "Sin stock: 1 (Tarta de queso (0))" in msg
    assert "Bajo mínimos: 1 (Vino tinto (3, mínimo 5))" in msg
    assert "Más stock: Cerveza (40)" in msg and "Croquetas" not in msg
    assert oa["message"] != LLM_STUB and not approvals(db, ua)
    ob = say(client, ub, "¿cómo está el inventario?")
    assert "1 referencia," in ob["message"] and "Croquetas (12)" in ob["message"]
    assert "Cerveza" not in ob["message"] and "Vino" not in ob["message"]


def test_chat_vacio_honesto_y_sin_control_de_stock_no_cuenta_ceros(db, client):
    uv, _ = _user(db)
    out = say(client, uv, "¿cómo está el inventario?")
    assert out["message"] == "No tienes productos dados de alta en el TPV ni en el inventario de tu empresa."
    u, c = _user(db)
    for n in ("Café", "Caña", "Tostada", "Menú"):
        _tpv(db, u, c, n, None)
    out = say(client, u, "¿qué productos hay sin stock?")
    assert "4 referencias, pero ninguna lleva control de stock" in out["message"]
    assert "0 referencias" not in out["message"] and "Sin stock" not in out["message"]


# ----------------------------------------------------------------------------- HTTP con login real
def test_endpoints_http_del_agente_con_login_real_y_aislados(db, client):
    ua, ca = _restaurante_a(db)
    ub, cb = _restaurante_b(db)
    ha, hb = _login(client, ua), _login(client, ub)
    # Chat del propio agente (workspace AFRODITA)
    r = client.post(f"{P}/chat/afrodita/chat", headers=ha,
                    json={"message": "¿cómo está el inventario?", "thread_id": f"t-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["message"] != LLM_STUB and "Bajo mínimos: 1 (Vino tinto (3, mínimo 5))" in body["message"]
    assert "Croquetas" not in body["message"]
    # Ejecutor de agentes (THALOS guard)
    r = client.post(f"{P}/zeus-core/agent/execute", headers=hb,
                    json={"agent": "AFRODITA", "action": "get_inventory_status", "payload": {}})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["success"] and d["company_id"] == cb.id
    assert [i["name"] for i in d["data"]["items"]] == ["Croquetas"]
    # Sin credenciales: rechazo controlado, no un falso éxito
    r = client.post(f"{P}/zeus-core/agent/execute",
                    json={"agent": "AFRODITA", "action": "get_inventory_status", "payload": {}})
    assert r.status_code in (401, 403), r.text
