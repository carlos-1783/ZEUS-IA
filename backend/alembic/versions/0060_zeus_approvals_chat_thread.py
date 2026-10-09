"""zeus_pending_approvals: thread_id + expires_at (estado unico de confirmacion chat/workspace)

Revision ID: 0060
Revises: 0059
Create Date: 2026-10-05

J3b: la vista previa del chat crea una fila en zeus_pending_approvals (unico
estado de confirmacion). thread_id ata la fila al hilo de chat del usuario y
expires_at fija su caducidad (15 min).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None

_TABLE = "zeus_pending_approvals"
_IDX = "ix_zeus_pending_approvals_thread_id"


def upgrade() -> None:
    insp = inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns(_TABLE)}
    with op.batch_alter_table(_TABLE) as batch_op:
        if "thread_id" not in cols:
            batch_op.add_column(sa.Column("thread_id", sa.String(length=128), nullable=True))
        if "expires_at" not in cols:
            batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    idx = {i["name"] for i in inspect(op.get_bind()).get_indexes(_TABLE)}
    if _IDX not in idx:
        op.create_index(_IDX, _TABLE, ["thread_id"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    idx = {i["name"] for i in insp.get_indexes(_TABLE)}
    if _IDX in idx:
        op.drop_index(_IDX, table_name=_TABLE)
    cols = {c["name"] for c in insp.get_columns(_TABLE)}
    with op.batch_alter_table(_TABLE) as batch_op:
        if "expires_at" in cols:
            batch_op.drop_column("expires_at")
        if "thread_id" in cols:
            batch_op.drop_column("thread_id")
