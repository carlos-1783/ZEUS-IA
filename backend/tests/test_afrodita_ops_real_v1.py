"""Tests AFRODITA OPS real movement and route persistence."""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.db.base import Base, SessionLocal, engine
from app.models.erp import InventoryMovementType, Product, ProductCategory, ProductStatus
from app.models.ops_route import OpsRoute
from app.models.user import User
from services.afrodita_ops_service_v1 import (
    create_inventory_movement,
    create_ops_route,
    warehouse_summary,
)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def user(db):
    u = User(
        email=f"ops-{uuid.uuid4().hex}@test.local",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def product(db):
    p = Product(
        sku=f"SKU-{uuid.uuid4().hex[:8]}",
        name="Test Product OPS",
        price=10.0,
        track_inventory=True,
        quantity_on_hand=100.0,
        low_stock_threshold=5.0,
        category=ProductCategory.GOODS,
        status=ProductStatus.ACTIVE,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_create_movement_updates_stock(db, user, product):
    with patch.dict(
        os.environ,
        {"AFRODITA_EXECUTION_ENABLED": "true", "AFRODITA_READ_ONLY_MODE": "false"},
        clear=False,
    ):
        out = create_inventory_movement(
            db,
            user,
            product_id=product.id,
            movement_type="adjustment",
            quantity=-10.0,
            reference="test-ops",
        )
        db.commit()
    assert out["stock_after"] == 90.0
    db.refresh(product)
    assert float(product.quantity_on_hand) == 90.0


def test_create_route_persists(db, user):
    with patch.dict(
        os.environ,
        {"AFRODITA_EXECUTION_ENABLED": "true", "AFRODITA_READ_ONLY_MODE": "false"},
        clear=False,
    ):
        out = create_ops_route(
            db,
            user,
            origin="Madrid",
            destination="Barcelona",
            deliveries=[{"id": "D1"}, {"id": "D2"}],
        )
        db.commit()
    assert out["route"]["distance"] > 0
    row = db.query(OpsRoute).filter(OpsRoute.id == out["route"]["id"]).first()
    assert row is not None
    assert row.origin == "Madrid"


def test_movement_rejects_negative_stock(db, user, product):
    with patch.dict(
        os.environ,
        {"AFRODITA_EXECUTION_ENABLED": "true", "AFRODITA_READ_ONLY_MODE": "false"},
        clear=False,
    ):
        with pytest.raises(HTTPException) as exc:
            create_inventory_movement(
                db,
                user,
                product_id=product.id,
                movement_type=InventoryMovementType.SALE.value,
                quantity=-500.0,
            )
        assert exc.value.status_code == 422


def test_warehouse_summary(db, user, product):
    _ = product
    summary = warehouse_summary(db, user)
    assert summary["implemented"] is True
    assert summary["total_skus"] >= 1
