"""Fase 2 / auditoria final #15 reserva publica: WhatsApp solo con casilla de consentimiento + limites por slug/telefono.

Dobles SOLO en test (cliente Twilio y envio de email); endpoints, THALOS y BD reales
(desechable). Ver envios_consentimiento_comun.py."""

from __future__ import annotations

from envios_consentimiento_comun import *  # noqa: F401,F403
from envios_consentimiento_comun import (  # noqa: F401  (fixtures)
    client, db, mail, public_base, twilio, _auth, _campaign, _customer, _outbound, _phone, _seed,
)


# ------------------------------------------------------------------ #15 reserva publica


def _reserva(client, slug, phone, consent=None):
    body = {"guest_name": "Luis", "guest_phone": phone, "reservation_date": "2026-11-20",
            "reservation_time": "21:00", "num_guests": 2}
    if consent is not None:
        body["whatsapp_consent"] = consent
    return client.post(f"/api/v1/p/{slug}/reservations", json=body)


def test_reserva_publica_sin_consentimiento_no_envia_whatsapp(db, client, twilio):
    user, co = _seed(db, "res")
    phone = _phone()
    r = _reserva(client, user.public_site_slug, phone)
    assert r.status_code == 200, r.text
    assert r.json()["whatsapp_confirmation"] == "no_consent"
    assert twilio.sent == []
    db.expire_all()
    res = db.get(Reservation, r.json()["id"])
    assert res.whatsapp_consent is False and res.company_id == co.id


def test_reserva_publica_con_consentimiento_envia_y_registra(db, client, twilio):
    user, co = _seed(db, "resok")
    phone = _phone()
    r = _reserva(client, user.public_site_slug, phone, consent=True)
    assert r.status_code == 200, r.text
    assert r.json()["whatsapp_confirmation"] == "sent"
    assert [m["to"] for m in twilio.sent] == [f"whatsapp:{phone}"]
    db.expire_all()
    res = db.get(Reservation, r.json()["id"])
    assert res.whatsapp_consent is True and res.whatsapp_consent_at is not None
    rows = _outbound(db, company_id=co.id, purpose="reservation_confirmation")
    assert [(x.status, x.recipient_ref_id) for x in rows] == [("sent", res.id)]


def test_reserva_publica_limite_por_telefono_y_por_slug(db, client, twilio, monkeypatch):
    monkeypatch.setenv("RESERVATION_LIMIT_PER_PHONE_PER_DAY", "2")
    monkeypatch.setenv("RESERVATION_LIMIT_PER_SLUG_PER_HOUR", "3")
    user, _ = _seed(db, "reslim")
    phone = _phone()
    codes = [_reserva(client, user.public_site_slug, phone, consent=True).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert len(twilio.sent) == 2
    assert _reserva(client, user.public_site_slug, _phone()).status_code == 200  # 3a del slug
    assert _reserva(client, user.public_site_slug, _phone()).status_code == 429  # slug lleno


def test_whatsapp_de_confirmacion_limitado_por_telefono_entre_negocios(db, client, twilio, monkeypatch):
    monkeypatch.setenv("PUBLIC_WHATSAPP_LIMIT_PER_PHONE_PER_DAY", "1")
    a, _ = _seed(db, "resx1")
    b, _ = _seed(db, "resx2")
    phone = _phone()
    assert _reserva(client, a.public_site_slug, phone, consent=True).json()["whatsapp_confirmation"] == "sent"
    r = _reserva(client, b.public_site_slug, phone, consent=True)
    assert r.status_code == 200 and r.json()["whatsapp_confirmation"] == "rate_limited"
    assert len(twilio.sent) == 1
