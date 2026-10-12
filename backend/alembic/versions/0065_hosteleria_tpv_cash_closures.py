"""tpv_cash_closures: cierre de caja del TPV persistido por empresa

Revision ID: 0065_hosteleria
Revises: 0064
Create Date: 2026-10-12

Fase 2 / vertical hosteleria: el cierre de caja se calculaba en memoria sin sumar las
ventas (expected_cash = initial_cash) y no se guardaba. Esta tabla registra cada cierre
con su periodo, los totales reales de tpv_sales de la empresa y el descuadre.

Solo crea una tabla nueva (idempotente: no hace nada si ya existe). No toca datos.
Rollback: `alembic downgrade 0064` elimina la tabla (se pierden los cierres registrados).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0065_hosteleria"
down_revision = "0064"
branch_labels = None
depends_on = None

_TABLE = "tpv_cash_closures"


def upgrade() -> None:
    if _TABLE in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("terminal_id", sa.String(length=100), nullable=False),
        sa.Column("employee_code", sa.String(length=100), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sales_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cash_sales_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("card_sales_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("other_sales_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sales_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("initial_cash", sa.Numeric(12, 2), nullable=False),
        sa.Column("final_cash", sa.Numeric(12, 2), nullable=False),
        sa.Column("expected_cash", sa.Numeric(12, 2), nullable=False),
        sa.Column("difference", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tpv_cash_closures_id", _TABLE, ["id"])
    op.create_index("ix_tpv_cash_closures_company_id", _TABLE, ["company_id"])
    op.create_index("ix_tpv_cash_closures_user_id", _TABLE, ["user_id"])


def downgrade() -> None:
    if _TABLE not in inspect(op.get_bind()).get_table_names():
        return
    op.drop_index("ix_tpv_cash_closures_user_id", table_name=_TABLE)
    op.drop_index("ix_tpv_cash_closures_company_id", table_name=_TABLE)
    op.drop_index("ix_tpv_cash_closures_id", table_name=_TABLE)
    op.drop_table(_TABLE)
