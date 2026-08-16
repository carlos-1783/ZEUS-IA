"""products: add company_id/created_by for multi-tenant isolation

Revision ID: 0043
Revises: 0042
Create Date: 2026-08-17

Contexto: el endpoint /api/v1/products/ no filtraba por empresa porque el
modelo Product no tenia ninguna columna de tenant. Cualquier usuario
autenticado podia leer/editar/borrar productos de otra empresa. Esta
migracion añade `company_id` (FK a companies, nullable) y `created_by`
(FK a users, nullable) siguiendo el mismo patron que 0012 aplico a
tpv_products/tpv_sales/invoices.

No se hace backfill de company_id para productos existentes porque el
modelo no tenia ninguna referencia de propietario (ni user_id ni
company_id) antes de esta migracion, por lo que no hay forma fiable de
inferir a que empresa pertenecia cada producto legacy. Los productos
existentes quedaran con company_id NULL: bajo el filtro de tenant nuevo
(company_id IN (:cids_del_usuario)) esas filas dejan de ser visibles
para cualquier tenant hasta que se les asigne una empresa manualmente.
Se prefiere "ocultar" ese dato huerfano antes que seguir filtrandolo
entre empresas.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("products")}

    if "company_id" not in cols:
        op.add_column("products", sa.Column("company_id", sa.Integer(), nullable=True))
        op.create_index(op.f("ix_products_company_id"), "products", ["company_id"], unique=False)
        op.create_foreign_key(
            "fk_products_company_id",
            "products",
            "companies",
            ["company_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if "created_by" not in cols:
        op.add_column("products", sa.Column("created_by", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_products_created_by",
            "products",
            "users",
            ["created_by"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("products")}

    if "created_by" in cols:
        op.drop_constraint("fk_products_created_by", "products", type_="foreignkey")
        op.drop_column("products", "created_by")

    if "company_id" in cols:
        op.drop_constraint("fk_products_company_id", "products", type_="foreignkey")
        op.drop_index(op.f("ix_products_company_id"), table_name="products")
        op.drop_column("products", "company_id")
