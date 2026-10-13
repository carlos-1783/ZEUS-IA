"""Fase 2 / auditoria final #3 campana PERSEO solo a clientes con consentimiento + baja firmada.

Dobles SOLO en test (cliente Twilio y envio de email); endpoints, THALOS y BD reales
(desechable). Ver envios_consentimiento_comun.py."""

from __future__ import annotations

from envios_consentimiento_comun import *  # noqa: F401,F403
from envios_consentimiento_comun import (  # noqa: F401  (fixtures)
    client, db, mail, public_base, twilio, _auth, _campaign, _customer, _outbound, _phone, _seed,
)


# ------------------------------------------------------------------ #3 campana


def test_campana_solo_a_clientes_con_consentimiento_y_con_enlace_de_baja(db, mail, public_base):
    user, co = _seed(db, "camp")
    ok = _customer(db, co, consent=True, name="Ana")
    sin = _customer(db, co, consent=False, name="Bea")
    baja = _customer(db, co, consent=True, unsubscribed=True, name="Carla")
    _, otra = _seed(db, "camp-otra")
    ajeno = _customer(db, otra, consent=True, name="Ajeno")

    res = _campaign(db, user, co)

    assert res.success is True and res.executed is True
    assert [c["to"] for c in mail] == [ok.email]
    body = mail[0]["content"]
    token = oc.issue_unsubscribe_token(co.id, ok.id)
    assert f"{BASE}/api/v1/p/unsubscribe?token={token}" in body and "Darme de baja" in body
    assert sin.email not in str(mail) and baja.email not in str(mail) and ajeno.email not in str(mail)
    rows = _outbound(db, company_id=co.id, purpose="campaign")
    assert [(r.status, r.recipient_ref_id) for r in rows] == [("sent", ok.id)]
    assert ok.email not in rows[0].recipient_masked
    assert res.metrics["recipients"] == 1 and res.metrics["excluded_no_consent"] == 2


def test_campana_sin_consentimientos_no_envia_nada_y_lo_dice(db, mail, public_base):
    user, co = _seed(db, "camp0")
    _customer(db, co, consent=False)
    _customer(db, co, consent=False)

    res = _campaign(db, user, co)

    assert res.success is False and res.executed is False
    assert "consentimiento" in res.message
    assert mail == []
    assert res.metrics == {"recipients": 0, "excluded_no_consent": 2, "company_id": co.id}
    assert "consentimiento" in handlers.preview_send_campaign(db, user, ZeusAction(
        action_type="send_campaign", company_id=co.id, user_id=user.id, payload={}))["message"]


def test_campana_sin_public_base_url_se_bloquea_sin_enviar(db, mail, monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "", raising=False)
    user, co = _seed(db, "campnourl")
    _customer(db, co, consent=True)

    res = _campaign(db, user, co)

    assert res.success is False and res.executed is False
    assert "PUBLIC_BASE_URL" in res.message
    assert mail == []


def test_baja_por_enlace_marca_al_cliente_y_la_campana_lo_excluye(db, client, mail, public_base):
    user, co = _seed(db, "unsub")
    c = _customer(db, co, consent=True)
    token = oc.issue_unsubscribe_token(co.id, c.id)

    page = client.get("/api/v1/p/unsubscribe", params={"token": token})
    assert page.status_code == 200 and "<form" in page.text
    db.expire_all()
    assert db.get(Customer, c.id).marketing_consent is True  # GET no da de baja (prefetch de correo)

    r = client.post("/api/v1/p/unsubscribe", params={"token": token})
    assert r.status_code == 200, r.text
    db.expire_all()
    row = db.get(Customer, c.id)
    assert row.marketing_consent is False and row.marketing_unsubscribed_at is not None

    res = _campaign(db, user, co)
    assert res.success is False and mail == []


def test_baja_con_token_falso_o_de_otra_empresa_no_toca_nada(db, client):
    _, co = _seed(db, "unsubbad")
    _, otra = _seed(db, "unsubbad2")
    c = _customer(db, co, consent=True)
    falso = oc.issue_unsubscribe_token(otra.id, c.id)  # firma valida pero empresa equivocada
    manipulado = oc.issue_unsubscribe_token(co.id, c.id)[:-1] + "0"

    for tok in (falso, manipulado, "basura"):
        r = client.post("/api/v1/p/unsubscribe", params={"token": tok})
        assert r.status_code == 400, (tok, r.text)
    db.expire_all()
    assert db.get(Customer, c.id).marketing_consent is True


def test_consentimiento_se_registra_por_endpoint_y_no_cruza_empresas(db, client):
    user, co = _seed(db, "consent")
    other, _ = _seed(db, "consent2")
    c = _customer(db, co, consent=False)

    r = client.post(
        f"/api/v1/crm/customers/{c.id}/marketing-consent",
        json={"granted": True, "source": "formulario_tienda"},
        headers=_auth(user),
    )
    assert r.status_code == 200, r.text
    assert r.json()["marketing_consent"] is True and r.json()["marketing_consent_source"] == "formulario_tienda"

    r2 = client.post(
        f"/api/v1/crm/customers/{c.id}/marketing-consent", json={"granted": False}, headers=_auth(other)
    )
    assert r2.status_code == 404
    db.expire_all()
    assert db.get(Customer, c.id).marketing_consent is True
