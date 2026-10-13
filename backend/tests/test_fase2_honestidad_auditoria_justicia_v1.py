"""Fase 2 / honestidad final #9 — auditoria de sistema JUSTICIA sin ok=True fijo.

Cada comprobacion ejecuta el guard/servicio real que dice comprobar; lo no verificable sale
como GAP con evidencia NONE. Si el guard real deja de bloquear, la comprobacion pasa a FAIL.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.legal_document import LegalDocument
from app.models.user import User
from services import afrodita_finalization_v1
from services.justice_system_audit_v1 import run_system_audit


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _seed(db):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Aud {suf}", slug=f"aud-{suf}")
    u = User(email=f"aud_{suf}@example.test", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


def _by_check(out):
    return {c["check"]: c for c in out["conclusions"]}


def test_comprobaciones_reales(db):
    u, c = _seed(db)
    ou, oc = _seed(db)
    db.add_all([
        LegalDocument(user_id=u.id, company_id=c.id, doc_type="contract", content="a"),
        LegalDocument(user_id=ou.id, company_id=oc.id, doc_type="contract", content="b"),
        LegalDocument(user_id=ou.id, company_id=oc.id, doc_type="contract", content="c"),
    ])
    db.commit()
    checks = _by_check(run_system_audit(db, u))
    assert checks["workspace afrodita aislado (403)"]["status"] == "PASS"
    assert checks["fichaje facial deshabilitado"]["status"] == "PASS"
    assert checks["simulacion de rutas retirada (410)"]["status"] == "PASS"
    assert "rutas etiquetadas SIMULADO" not in checks
    legal = checks["justicia legal_documents en BD"]
    assert legal["status"] == "PASS" and legal["value"] == 1  # solo su empresa
    gap = checks["no usado como fuente de verdad RRHH/OPS"]
    assert gap["status"] == "GAP" and gap["evidence_source"] == "NONE"


def test_si_el_guard_deja_de_bloquear_es_fail(db, monkeypatch):
    u, _ = _seed(db)
    monkeypatch.setattr(afrodita_finalization_v1, "assert_workspace_isolated", lambda module: None)
    checks = _by_check(run_system_audit(db, u))
    iso = checks["workspace afrodita aislado (403)"]
    assert iso["status"] == "FAIL" and "facial_checkin" in iso["detail"]
