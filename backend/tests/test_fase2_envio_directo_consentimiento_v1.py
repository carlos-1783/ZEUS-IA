"""Fase 2 / auditoria final #4 /integrations/{whatsapp,email}/send: destinatario de la empresa con consentimiento + limite.

Dobles SOLO en test (cliente Twilio y envio de email); endpoints, THALOS y BD reales
(desechable). Ver envios_consentimiento_comun.py."""

from __future__ import annotations

from envios_consentimiento_comun import *  # noqa: F401,F403
from envios_consentimiento_comun import (  # noqa: F401  (fixtures)
    client, db, mail, public_base, twilio, _auth, _campaign, _customer, _outbound, _phone, _seed,
)


# ------------------------------------------------------------------ #4 envio directo


def test_envio_directo_a_cliente_de_otra_empresa_se_bloquea(db, client, twilio, mail, public_base):
    user, co = _seed(db, "dir")
    _, otra = _seed(db, "dir-otra")
    phone = _phone()
    ajeno = _customer(db, otra, consent=True, phone=phone)

    r = client.post("/api/v1/integrations/whatsapp/send", json={"to_number": phone, "message": "hola"},
                    headers=_auth(user))
    assert r.status_code == 403, r.text
    r = client.post("/api/v1/integrations/email/send",
                    json={"to_email": ajeno.email, "subject": "s", "content": "c"}, headers=_auth(user))
    assert r.status_code == 403, r.text
    assert twilio.sent == [] and mail == []
    blocked = _outbound(db, company_id=co.id, status="blocked")
    assert len(blocked) == 2 and all(b.detail == "no es cliente ni empleado de tu empresa" for b in blocked)


def test_envio_directo_a_cliente_propio_sin_consentimiento_se_bloquea(db, client, twilio, mail, public_base):
    user, co = _seed(db, "dirsin")
    phone = _phone()
    c = _customer(db, co, consent=False, phone=phone)

    r = client.post("/api/v1/integrations/whatsapp/send", json={"to_number": phone, "message": "hola"},
                    headers=_auth(user))
    assert r.status_code == 403 and "consentimiento" in r.json()["detail"]
    r = client.post("/api/v1/integrations/email/send",
                    json={"to_email": c.email, "subject": "s", "content": "c"}, headers=_auth(user))
    assert r.status_code == 403
    assert twilio.sent == [] and mail == []


def test_envio_directo_a_cliente_con_consentimiento_y_empleado(db, client, twilio, mail, public_base):
    user, co = _seed(db, "dirok")
    phone = _phone()
    c = _customer(db, co, consent=True, phone=phone)
    emp_phone = _phone()
    db.add(CompanyEmployee(company_id=co.id, full_name="Empleado", employee_code=f"E{uuid.uuid4().hex[:5]}",
                           phone=emp_phone, is_active=True))
    db.commit()

    r = client.post("/api/v1/integrations/whatsapp/send",
                    json={"to_number": phone.replace("+34", "0034"), "message": "Tu pedido esta listo"},
                    headers=_auth(user))
    assert r.status_code == 200, r.text
    assert twilio.sent[0]["to"] == f"whatsapp:{phone}"
    assert "/api/v1/p/unsubscribe?token=" in twilio.sent[0]["body"]  # cliente: siempre con baja

    r = client.post("/api/v1/integrations/whatsapp/send", json={"to_number": emp_phone, "message": "Turno"},
                    headers=_auth(user))
    assert r.status_code == 200, r.text
    assert twilio.sent[1]["body"] == "Turno"  # empleado: comunicacion interna, sin pie comercial

    r = client.post("/api/v1/integrations/email/send",
                    json={"to_email": c.email, "subject": "s", "content": "<p>c</p>"}, headers=_auth(user))
    assert r.status_code == 200, r.text
    assert "Darme de baja" in mail[0]["content"]

    sent = _outbound(db, company_id=co.id, purpose="direct", status="sent")
    assert sorted((s.channel, s.recipient_kind) for s in sent) == [
        ("email", "customer"), ("whatsapp", "customer"), ("whatsapp", "employee")]
    assert all(phone not in (s.recipient_masked or "") for s in sent)


def test_envio_directo_limite_por_empresa(db, client, twilio, monkeypatch, public_base):
    monkeypatch.setenv("OUTBOUND_DIRECT_LIMIT_PER_HOUR", "2")
    user, co = _seed(db, "dirlim")
    phone = _phone()
    _customer(db, co, consent=True, phone=phone)
    codes = [
        client.post("/api/v1/integrations/whatsapp/send", json={"to_number": phone, "message": "x"},
                    headers=_auth(user)).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]
    assert len(twilio.sent) == 2
    # El limite es por empresa: otra empresa sigue pudiendo enviar.
    user2, co2 = _seed(db, "dirlim2")
    phone2 = _phone()
    _customer(db, co2, consent=True, phone=phone2)
    assert client.post("/api/v1/integrations/whatsapp/send", json={"to_number": phone2, "message": "x"},
                       headers=_auth(user2)).status_code == 200


def test_envio_directo_superusuario_plataforma(db, client, twilio, public_base):
    admin, _ = _seed(db, "dirsu", superuser=True)
    phone = _phone()
    r = client.post("/api/v1/integrations/whatsapp/send", json={"to_number": phone, "message": "aviso"},
                    headers=_auth(admin))
    assert r.status_code == 200, r.text
    rows = [r for r in _outbound(db, purpose="platform") if r.user_id == admin.id]
    assert len(rows) == 1 and rows[0].company_id is None and rows[0].status == "sent"


def test_envio_directo_sin_scope_ni_token(db, client, twilio):
    user, _ = _seed(db, "dirscope")
    r = client.post("/api/v1/integrations/whatsapp/send", json={"to_number": _phone(), "message": "x"},
                    headers=_auth(user, scopes=("marketing:read",)))
    assert r.status_code == 403
    r = client.post("/api/v1/integrations/whatsapp/send", json={"to_number": _phone(), "message": "x"})
    assert r.status_code == 401
    assert twilio.sent == []
