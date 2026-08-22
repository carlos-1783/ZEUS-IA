"""invoices.tpv_sale_id — enlace real factura <-> venta TPV (puente RAFAEL/TPV)

Revision ID: 0043
Revises: 0042
"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"
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
        op.add_column(
            "invoices",
            sa.Column(
                "tpv_sale_id",
                sa.Integer(),
                sa.ForeignKey("tpv_sales.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index("ix_invoices_tpv_sale_id", "invoices", ["tpv_sale_id"])
        # Unicidad (permite NULL múltiples; evita 2 facturas para la misma venta TPV)
        op.create_unique_constraint(
            "uq_invoices_tpv_sale_id", "invoices", ["tpv_sale_id"]
        )


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    if "invoices" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("invoices")}
    if "tpv_sale_id" in cols:
        try:
            op.drop_constraint("uq_invoices_tpv_sale_id", "invoices", type_="unique")
        except Exception:
            pass
        try:
            op.drop_index("ix_invoices_tpv_sale_id", table_name="invoices")
        except Exception:
            pass
        op.drop_column("invoices", "tpv_sale_id")
