"""J12b: crear cliente por chat valida el email en la VISTA PREVIA con el mismo validador que la
ejecucion: email invalido -> aclaracion sin aprobacion; valido -> aprobacion como siempre."""

from __future__ import annotations

import uuid

from app.models.zeus_pending_approval import ZeusPendingApproval
from test_confirmacion_unica_v1 import (  # noqa: F401  (fixtures y ayudantes)
    _chat,
    _count_customers,
    _preview,
    _seed,
    client,
    db,
    sent,
)


def _approvals(db, user):
    db.expire_all()
    return db.query(ZeusPendingApproval).filter(ZeusPendingApproval.user_id == user.id).count()


def test_email_invalido_no_crea_aprobacion_y_pide_aclaracion(db, client, sent):
    user, company = _seed(db, with_customer=False)
    for bad in ("juan@dominio.test", "juan@empresa.invalid", "juan@localhost.local"):
        r = _chat(client, user, f"crear cliente Juan {bad}", thread="e-" + uuid.uuid4().hex[:6]).json()
        assert not r.get("approval_id") and r.get("needs_confirmation") is not True, (bad, r)
        assert r["executed_action"] is not True
        assert "email" in r["message"].lower(), (bad, r["message"])
    assert _approvals(db, user) == 0
    assert _count_customers(db, company.id) == 0


def test_email_valido_si_crea_aprobacion_y_cliente(db, client, sent):
    user, company = _seed(db, with_customer=False)
    thread = "ok-" + uuid.uuid4().hex[:6]
    aid = _preview(client, user, thread, f"crear cliente Juan juan_{uuid.uuid4().hex[:6]}@example.com")
    assert aid and _approvals(db, user) == 1 and _count_customers(db, company.id) == 0
    assert _chat(client, user, "confirmar", thread=thread).json()["executed_action"] is True
    assert _count_customers(db, company.id) == 1
