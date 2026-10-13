"""Fase 2 / Oficina — KPI "Alertas": una empresa nunca ve alertas de otra ni eventos globales."""

from __future__ import annotations

import uuid

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.compliance_event import ComplianceEvent
from app.models.user import User
from app.models.zeus_analytics import ZeusAlert
from services.zeus_analytics_real_v1 import _count_alerts, list_unresolved_alerts


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _user(db, superuser=False):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"A {suf}", slug=f"a-{suf}")
    u = User(email=f"al_{suf}@example.com", hashed_password=get_password_hash("TestPass1"),
             is_active=True, is_superuser=superuser)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u


def test_alerts_scoped_to_own_tenant(db):
    me, other = _user(db), _user(db)
    db.add_all([
        ZeusAlert(level="high", message="mia", user_id=me.id),
        ZeusAlert(level="high", message="ajena", user_id=other.id),
        ZeusAlert(level="high", message="resuelta", user_id=me.id, resolved=True),
    ])
    db.commit()
    assert _count_alerts(db, me) == 1
    msgs = [a["message"] for a in list_unresolved_alerts(db, me)]
    assert msgs == ["mia"]
    assert "ajena" not in [a["message"] for a in list_unresolved_alerts(db, me)]


def test_global_compliance_events_not_leaked_to_tenant(db):
    me = _user(db)
    db.add(ComplianceEvent(event_type=f"fuga_{uuid.uuid4().hex[:6]}", severity="high", source="test"))
    db.commit()
    # Antes: sin ZeusAlert propias, el cliente veia los compliance_events de toda la plataforma.
    assert _count_alerts(db, me) == 0
    assert list_unresolved_alerts(db, me) == []


def test_superuser_still_sees_platform_events(db):
    su = _user(db, superuser=True)
    et = f"plataforma_{uuid.uuid4().hex[:6]}"
    db.add(ComplianceEvent(event_type=et, severity="high", source="test"))
    db.commit()
    assert _count_alerts(db, su) >= 1
    assert et in [a["message"] for a in list_unresolved_alerts(db, su)]


def test_no_user_fail_closed(db):
    db.add(ZeusAlert(level="high", message="x", user_id=None))
    db.commit()
    assert _count_alerts(db, None) == 0
    assert list_unresolved_alerts(db, None) == []
