"""legal_documents + compliance_events — JUSTICIA force real mode

Revision ID: 0040
Revises: 0039
"""
from alembic import op
import sqlalchemy as sa

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()

    if "legal_documents" not in tables:
        op.create_table(
            "legal_documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("public_id", sa.String(36), nullable=False, unique=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
            sa.Column("doc_type", sa.String(64), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("owner_agent", sa.String(64), nullable=False, server_default="JUSTICIA"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("parent_id", sa.Integer(), sa.ForeignKey("legal_documents.id", ondelete="SET NULL"), nullable=True),
            sa.Column("signature_hash", sa.String(128), nullable=True),
            sa.Column("signer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_legal_documents_user_id", "legal_documents", ["user_id"])
        op.create_index("ix_legal_documents_status", "legal_documents", ["status"])
        op.create_index("ix_legal_documents_doc_type", "legal_documents", ["doc_type"])

    if "compliance_events" not in tables:
        op.create_table(
            "compliance_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("public_id", sa.String(36), nullable=False, unique=True),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("severity", sa.String(16), nullable=False, server_default="low"),
            sa.Column("source", sa.String(64), nullable=False),
            sa.Column("details_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_compliance_events_event_type", "compliance_events", ["event_type"])
        op.create_index("ix_compliance_events_severity", "compliance_events", ["severity"])


def downgrade() -> None:
    op.drop_index("ix_compliance_events_severity", table_name="compliance_events")
    op.drop_index("ix_compliance_events_event_type", table_name="compliance_events")
    op.drop_table("compliance_events")
    op.drop_index("ix_legal_documents_doc_type", table_name="legal_documents")
    op.drop_index("ix_legal_documents_status", table_name="legal_documents")
    op.drop_index("ix_legal_documents_user_id", table_name="legal_documents")
    op.drop_table("legal_documents")
