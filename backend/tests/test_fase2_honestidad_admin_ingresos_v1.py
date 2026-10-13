"""Fase 2 / honestidad final #12 — /admin/stats y /admin/revenue-chart declaran que los
"ingresos" son teoricos segun plan (no hay tabla de pagos de Stripe en el repo)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_active_user, get_current_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.user import User


@pytest.fixture()
def admin():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Adm {suf}", slug=f"adm-{suf}")
    u = User(email=f"adm_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             is_active=True, is_superuser=True, plan="growth")
    s.add_all([c, u])
    s.flush()
    s.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    s.commit()
    s.refresh(u)
    app.dependency_overrides[get_current_active_user] = lambda: u
    app.dependency_overrides[get_current_user] = lambda: u
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
        app.dependency_overrides.pop(get_current_user, None)
        s.close()


def test_stats_declara_ingresos_teoricos(admin):
    r = admin.get("/api/v1/admin/stats")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["revenue_basis"] == "theoretical_plan_price"
    assert "No son cobros reales" in b["revenue_note"]
    assert b["theoretical_revenue"]["monthly"] == b["stats"]["monthly_revenue"] >= 497


def test_chart_leyendas_teoricas(admin):
    r = admin.get("/api/v1/admin/revenue-chart?months=3")
    assert r.status_code == 200, r.text
    b = r.json()
    labels = [d["label"] for d in b["chart_data"]["datasets"]]
    assert labels == ["Ingresos teóricos según plan (€)", "Altas teóricas según plan (€)"]
    assert b["revenue_basis"] == "theoretical_plan_price"
