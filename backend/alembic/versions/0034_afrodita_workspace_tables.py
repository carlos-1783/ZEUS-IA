"""afrodita workspace_files + workspace_playbooks

Revision ID: 0034
Revises: 0033
"""
from alembic import op
import sqlalchemy as sa

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())

    if "workspace_files" not in existing:
        op.create_table(
            "workspace_files",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
            sa.Column("agent_name", sa.String(32), nullable=False, server_default="AFRODITA"),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_workspace_files_user_id", "workspace_files", ["user_id"])
        op.create_index("ix_workspace_files_company_id", "workspace_files", ["company_id"])
        op.create_index("ix_workspace_files_agent_name", "workspace_files", ["agent_name"])

    if "workspace_playbooks" not in existing:
        op.create_table(
            "workspace_playbooks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
            sa.Column("agent_name", sa.String(32), nullable=False, server_default="AFRODITA"),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_workspace_playbooks_user_id", "workspace_playbooks", ["user_id"])
        op.create_index("ix_workspace_playbooks_company_id", "workspace_playbooks", ["company_id"])
        op.create_index("ix_workspace_playbooks_agent_name", "workspace_playbooks", ["agent_name"])


def downgrade() -> None:
    op.drop_index("ix_workspace_playbooks_agent_name", table_name="workspace_playbooks")
    op.drop_index("ix_workspace_playbooks_company_id", table_name="workspace_playbooks")
    op.drop_index("ix_workspace_playbooks_user_id", table_name="workspace_playbooks")
    op.drop_table("workspace_playbooks")
    op.drop_index("ix_workspace_files_agent_name", table_name="workspace_files")
    op.drop_index("ix_workspace_files_company_id", table_name="workspace_files")
    op.drop_index("ix_workspace_files_user_id", table_name="workspace_files")
    op.drop_table("workspace_files")
