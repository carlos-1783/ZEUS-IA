"""Workspace: company_id y visible_in_workspace en document_approvals.

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_approvals",
        sa.Column("company_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_document_approvals_company_id"),
        "document_approvals",
        ["company_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_document_approvals_company_id",
        "document_approvals",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "document_approvals",
        sa.Column(
            "visible_in_workspace",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("document_approvals", "visible_in_workspace")
    op.drop_constraint("fk_document_approvals_company_id", "document_approvals", type_="foreignkey")
    op.drop_index(op.f("ix_document_approvals_company_id"), table_name="document_approvals")
    op.drop_column("document_approvals", "company_id")
