"""perseo_jobs queue table

Revision ID: 0038
Revises: 0037
"""
from alembic import op
import sqlalchemy as sa

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    if "perseo_jobs" in inspect(bind).get_table_names():
        return
    op.create_table(
        "perseo_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.String(36), nullable=True),
        sa.Column("input_json", sa.Text(), nullable=True),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_perseo_jobs_job_id", "perseo_jobs", ["job_id"], unique=True)
    op.create_index("ix_perseo_jobs_status", "perseo_jobs", ["status"])
    op.create_index("ix_perseo_jobs_user_id", "perseo_jobs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_perseo_jobs_user_id", table_name="perseo_jobs")
    op.drop_index("ix_perseo_jobs_status", table_name="perseo_jobs")
    op.drop_index("ix_perseo_jobs_job_id", table_name="perseo_jobs")
    op.drop_table("perseo_jobs")
