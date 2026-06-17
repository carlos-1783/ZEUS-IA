"""thalos_workspace_items — thalos_workspace_connection_v1

Revision ID: 0033
Revises: 0032
"""
from alembic import op
import sqlalchemy as sa

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    if "thalos_workspace_items" in inspect(bind).get_table_names():
        return

    op.create_table(
        "thalos_workspace_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False, unique=True),
        sa.Column("item_type", sa.String(16), nullable=False),
        sa.Column("workspace_document_id", sa.Integer(), sa.ForeignKey("document_approvals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="completed"),
        sa.Column("data_size_kb", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_thalos_workspace_items_item_type", "thalos_workspace_items", ["item_type"])
    op.create_index("ix_thalos_workspace_items_company_id", "thalos_workspace_items", ["company_id"])
    op.create_index("ix_thalos_workspace_items_user_id", "thalos_workspace_items", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_thalos_workspace_items_user_id", table_name="thalos_workspace_items")
    op.drop_index("ix_thalos_workspace_items_company_id", table_name="thalos_workspace_items")
    op.drop_index("ix_thalos_workspace_items_item_type", table_name="thalos_workspace_items")
    op.drop_table("thalos_workspace_items")
