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
    with op.batch_alter_table("document_approvals") as batch_op:
        batch_op.create_foreign_key(
            "fk_document_approvals_company_id",
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
    with op.batch_alter_table("document_approvals") as batch_op:
        batch_op.drop_column("visible_in_workspace")
        batch_op.drop_constraint("fk_document_approvals_company_id", type_="foreignkey")
        batch_op.drop_index(op.f("ix_document_approvals_company_id"))
        batch_op.drop_column("company_id")
