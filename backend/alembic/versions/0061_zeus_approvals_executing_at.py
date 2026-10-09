"""zeus_pending_approvals: executing_at (deteccion de ejecuciones interrumpidas)

Revision ID: 0061
Revises: 0060
Create Date: 2026-10-07

J2b: execute_approval marca executing_at al reclamar la ejecucion; recover_stuck_approvals
usa esa marca para pasar a `failed` las filas que quedaron en `executing` (proceso muerto).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None

_TABLE = "zeus_pending_approvals"


def upgrade() -> None:
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(_TABLE)}
    if "executing_at" not in cols:
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(sa.Column("executing_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(_TABLE)}
    if "executing_at" in cols:
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.drop_column("executing_at")
