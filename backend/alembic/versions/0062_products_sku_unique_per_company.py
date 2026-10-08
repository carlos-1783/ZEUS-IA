"""products/product_variants: SKU unico por empresa/producto en vez de global

Revision ID: 0062
Revises: 0061
Create Date: 2026-10-08

JARVIS J5d-resto (punto 1, severidad baja-media): `sku` era UNIQUE a nivel
de toda la tabla `products` (sin company_id), lo que permitia un oraculo de
enumeracion cruzada entre empresas: cualquier usuario autenticado podia
comprobar si un SKU concreto estaba en uso por OTRA empresa con solo
intentar crear un producto con ese codigo y observar si la API lo
rechazaba por duplicado -- sin tener ninguna relacion con esa empresa
ajena. Lo mismo aplicaba a `product_variants.sku`.

Se sustituye por una restriccion unica compuesta:
  - products: UNIQUE(company_id, sku) en lugar de UNIQUE(sku).
  - product_variants: UNIQUE(product_id, sku) en lugar de UNIQUE(sku)
    (ProductVariant no tiene company_id propio; hereda el scope de tenant
    de su Product via product_id).

Esto permite que dos empresas distintas usen el mismo codigo de SKU en sus
catalogos independientes (escenario de negocio legitimo) y hace que la
comprobacion de duplicados del endpoint (ver app/api/v1/endpoints/products.py)
se pueda acotar al scope de la propia empresa sin que la base de datos
vuelva a imponer la unicidad global por detras.

No se requiere backfill: la restriccion compuesta es estrictamente mas
permisiva que la global que sustituye, por lo que cualquier dato existente
que ya cumplia UNIQUE(sku) cumple trivialmente UNIQUE(company_id, sku) y
UNIQUE(product_id, sku).

El indice simple (no unico) sobre `sku` se conserva para que las busquedas
por SKU (p.ej. list_products con `search=`) sigan siendo eficientes.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def _index_names(bind, table: str) -> set:
    return {ix["name"] for ix in inspect(bind).get_indexes(table)}


def _unique_constraint_names(bind, table: str) -> set:
    return {uc["name"] for uc in inspect(bind).get_unique_constraints(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # --- products -------------------------------------------------------
    if "ix_products_sku" in _index_names(bind, "products"):
        op.drop_index("ix_products_sku", table_name="products")
    op.create_index("ix_products_sku", "products", ["sku"], unique=False)

    if "uq_products_company_id_sku" not in _unique_constraint_names(bind, "products"):
        with op.batch_alter_table("products") as batch_op:
            batch_op.create_unique_constraint(
                "uq_products_company_id_sku", ["company_id", "sku"]
            )

    # --- product_variants -------------------------------------------------
    if "ix_product_variants_sku" in _index_names(bind, "product_variants"):
        op.drop_index("ix_product_variants_sku", table_name="product_variants")
    op.create_index("ix_product_variants_sku", "product_variants", ["sku"], unique=False)

    if "uq_product_variants_product_id_sku" not in _unique_constraint_names(bind, "product_variants"):
        with op.batch_alter_table("product_variants") as batch_op:
            batch_op.create_unique_constraint(
                "uq_product_variants_product_id_sku", ["product_id", "sku"]
            )


def downgrade() -> None:
    bind = op.get_bind()

    # --- product_variants -------------------------------------------------
    if "uq_product_variants_product_id_sku" in _unique_constraint_names(bind, "product_variants"):
        with op.batch_alter_table("product_variants") as batch_op:
            batch_op.drop_constraint("uq_product_variants_product_id_sku", type_="unique")
    if "ix_product_variants_sku" in _index_names(bind, "product_variants"):
        op.drop_index("ix_product_variants_sku", table_name="product_variants")
    op.create_index("ix_product_variants_sku", "product_variants", ["sku"], unique=True)

    # --- products -------------------------------------------------------
    if "uq_products_company_id_sku" in _unique_constraint_names(bind, "products"):
        with op.batch_alter_table("products") as batch_op:
            batch_op.drop_constraint("uq_products_company_id_sku", type_="unique")
    if "ix_products_sku" in _index_names(bind, "products"):
        op.drop_index("ix_products_sku", table_name="products")
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)
