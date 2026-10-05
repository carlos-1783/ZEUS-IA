"""zeus_pending_approvals: result_json + executed_at (ejecucion servidor tras aprobar)

Revision ID: 0059
Revises: 0058
Create Date: 2026-10-05

J2: al aprobar, el servidor ejecuta la accion almacenada (agente, accion,
payload, empresa y usuario solicitante ya estaban persistidos). Se anaden el
resultado real (o error) y la marca de ejecucion. Estados nuevos de status
(columna String, sin enum): executing | executed | failed.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None

_TABLE = "zeus_pending_approvals"


def upgrade() -> None:
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(_TABLE)}
    with op.batch_alter_table(_TABLE) as batch_op:
        if "result_json" not in cols:
            batch_op.add_column(sa.Column("result_json", sa.Text(), nullable=True))
        if "executed_at" not in cols:
            batch_op.add_column(sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(_TABLE)}
    with op.batch_alter_table(_TABLE) as batch_op:
        if "executed_at" in cols:
            batch_op.drop_column("executed_at")
        if "result_json" in cols:
            batch_op.drop_column("result_json")
