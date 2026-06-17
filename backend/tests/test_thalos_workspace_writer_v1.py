"""Tests thalos_workspace_writer_v1."""

from __future__ import annotations

import uuid

import pytest  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.thalos_workspace_item import ThalosWorkspaceItem
from app.models.user import User
from services.thalos_workspace_writer_v1 import write_workspace_item


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed(db: Session):
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"tw_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        is_active=True,
    )
    company = Company(company_name=f"TW Co {suf}", slug=f"tw-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    return user, company


def test_write_workspace_item_persists_with_size(db: Session):
    user, company = _seed(db)
    row = write_workspace_item(
        db,
        user_id=user.id,
        company_id=company.id,
        item_type="audit",
        payload={
            "risk_level": "high",
            "pattern_alerts": [{"pattern": "failed login"}],
            "activities_scanned": 10,
        },
        persist_document=True,
    )
    db.commit()
    assert row is not None
    assert row.data_size_kb >= 1
    assert row.item_type == "audit"
    count = db.query(ThalosWorkspaceItem).filter(ThalosWorkspaceItem.user_id == user.id).count()
    assert count == 1
