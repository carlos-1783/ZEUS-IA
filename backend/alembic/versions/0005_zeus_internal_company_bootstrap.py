"""ZEUS_INTERNAL_COMPANY_BOOTSTRAP_002: companies, user_companies

Revision ID: 0005
Revises: 0004
Create Date: 2026-01-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("pilot_company", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=10), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companies_slug"), "companies", ["slug"], unique=True)
    op.create_index(op.f("ix_companies_company_name"), "companies", ["company_name"], unique=False)

    op.create_table(
        "user_companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "company_id", name="uq_user_companies_user_company"),
    )
    op.create_index(op.f("ix_user_companies_user_id"), "user_companies", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_companies_company_id"), "user_companies", ["company_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_companies_company_id"), table_name="user_companies")
    op.drop_index(op.f("ix_user_companies_user_id"), table_name="user_companies")
    op.drop_table("user_companies")
    op.drop_index(op.f("ix_companies_company_name"), table_name="companies")
    op.drop_index(op.f("ix_companies_slug"), table_name="companies")
    op.drop_table("companies")
