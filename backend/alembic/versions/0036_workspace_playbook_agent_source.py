"""workspace_playbooks agent_source column

Revision ID: 0036
Revises: 0035
"""
from alembic import op
import sqlalchemy as sa

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    if "workspace_playbooks" not in inspect(bind).get_table_names():
        return
    cols = {c["name"] for c in inspect(bind).get_columns("workspace_playbooks")}
    if "agent_source" not in cols:
        op.add_column(
            "workspace_playbooks",
            sa.Column("agent_source", sa.String(32), nullable=False, server_default="afrodita"),
        )
        op.create_index("ix_workspace_playbooks_agent_source", "workspace_playbooks", ["agent_source"])


def downgrade() -> None:
    op.drop_index("ix_workspace_playbooks_agent_source", table_name="workspace_playbooks")
    op.drop_column("workspace_playbooks", "agent_source")
