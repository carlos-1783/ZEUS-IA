"""Alinear document_approvals con el modelo (columnas fiscales / auditoría).

Algunas BD PostgreSQL tienen document_approvals sin las columnas de 0003
(p. ej. tabla creada manualmente o migraciones desalineadas). Esto provoca:
  UndefinedColumn: column "ticket_id" of relation "document_approvals" does not exist

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-06

"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def _existing_columns(bind) -> set:
    insp = sa.inspect(bind)
    if not insp.has_table("document_approvals"):
        return set()
    return {c["name"] for c in insp.get_columns("document_approvals")}


def _existing_indexes(bind) -> set:
    insp = sa.inspect(bind)
    if not insp.has_table("document_approvals"):
        return set()
    return {ix["name"] for ix in insp.get_indexes("document_approvals")}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _existing_columns(bind)
    if not cols:
        return

    specs = [
        ("ticket_id", sa.String(length=100), True),
        ("fiscal_document_type", sa.String(length=50), True),
        ("export_format", sa.String(length=20), True),
        ("exported_at", sa.DateTime(timezone=True), True),
        ("filed_external_at", sa.DateTime(timezone=True), True),
        ("approved_at", sa.DateTime(timezone=True), True),
        ("sent_at", sa.DateTime(timezone=True), True),
        ("audit_log_json", sa.Text(), True),
    ]
    for name, typ, nullable in specs:
        if name not in cols:
            op.add_column(
                "document_approvals",
                sa.Column(name, typ, nullable=nullable),
            )
            cols.add(name)

    idx = _existing_indexes(bind)
    if "ix_document_approvals_ticket_id" not in idx and "ticket_id" in cols:
        op.create_index(
            op.f("ix_document_approvals_ticket_id"),
            "document_approvals",
            ["ticket_id"],
            unique=False,
        )


def downgrade() -> None:
    """Solo revierte columnas fiscales de 0003 + índice; no toca approved_at/sent_at/audit si ya existían."""
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("document_approvals"):
        return
    idx = _existing_indexes(bind)
    if "ix_document_approvals_ticket_id" in idx:
        op.drop_index(
            op.f("ix_document_approvals_ticket_id"),
            table_name="document_approvals",
        )
    cols = _existing_columns(bind)
    for name in (
        "filed_external_at",
        "exported_at",
        "export_format",
        "fiscal_document_type",
        "ticket_id",
    ):
        if name in cols:
            op.drop_column("document_approvals", name)
