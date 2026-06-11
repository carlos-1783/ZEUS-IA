"""RAFAEL fiscal engine v2: expenses + file metadata on document_approvals

Revision ID: 0025
Revises: 0024
"""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    tables = set(insp.get_table_names())

    if "expenses" not in tables:
        op.create_table(
            "expenses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("supplier_name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("issue_date", sa.DateTime(), nullable=False),
            sa.Column("base_amount", sa.Float(), nullable=False, server_default="0"),
            sa.Column("tax_amount", sa.Float(), nullable=False, server_default="0"),
            sa.Column("tax_rate", sa.Float(), nullable=False, server_default="21"),
            sa.Column("category", sa.String(100), nullable=True),
            sa.Column("invoice_ref", sa.String(100), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_expenses_company_id", "expenses", ["company_id"])

    if "document_approvals" in tables:
        cols = {c["name"] for c in insp.get_columns("document_approvals")}
        if "file_path" not in cols:
            op.add_column("document_approvals", sa.Column("file_path", sa.String(500), nullable=True))
        if "file_size_bytes" not in cols:
            op.add_column("document_approvals", sa.Column("file_size_bytes", sa.Integer(), nullable=True))
        if "mime_type" not in cols:
            op.add_column("document_approvals", sa.Column("mime_type", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_table("expenses")
    for col in ("mime_type", "file_size_bytes", "file_path"):
        try:
            op.drop_column("document_approvals", col)
        except Exception:
            pass
