"""invoices.tpv_sale_id — enlace real factura <-> venta TPV (puente RAFAEL/TPV)

Revision ID: 0050
Revises: 0049

Nota de consolidación (feature/consolidacion-final): renumerada de "0044" a
"0050" al fusionar — colisionaba con "0044_role_check_constraints.py" (ya
mergeado). Encadenada tras "0049", sin cambios de lógica.
"""
from alembic import op
import sqlalchemy as sa

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    if "invoices" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("invoices")}
    if "tpv_sale_id" not in cols:
        with op.batch_alter_table("invoices") as batch_op:
            batch_op.add_column(
                sa.Column("tpv_sale_id", sa.Integer(), nullable=True),
            )
            batch_op.create_foreign_key(
                "fk_invoices_tpv_sale_id",
                "tpv_sales",
                ["tpv_sale_id"],
                ["id"],
                ondelete="SET NULL",
            )
            # Unicidad (permite NULL múltiples; evita 2 facturas para la misma venta TPV)
            batch_op.create_unique_constraint(
                "uq_invoices_tpv_sale_id", ["tpv_sale_id"]
            )
        op.create_index("ix_invoices_tpv_sale_id", "invoices", ["tpv_sale_id"])


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    if "invoices" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("invoices")}
    if "tpv_sale_id" in cols:
        existing_indexes = {ix["name"] for ix in insp.get_indexes("invoices")}
        existing_uniques = {uq["name"] for uq in insp.get_unique_constraints("invoices")}
        existing_fks = {fk["name"] for fk in insp.get_foreign_keys("invoices")}

        if "ix_invoices_tpv_sale_id" in existing_indexes:
            op.drop_index("ix_invoices_tpv_sale_id", table_name="invoices")

        with op.batch_alter_table("invoices") as batch_op:
            if "uq_invoices_tpv_sale_id" in existing_uniques:
                batch_op.drop_constraint("uq_invoices_tpv_sale_id", type_="unique")
            if "fk_invoices_tpv_sale_id" in existing_fks:
                batch_op.drop_constraint("fk_invoices_tpv_sale_id", type_="foreignkey")
            batch_op.drop_column("tpv_sale_id")
