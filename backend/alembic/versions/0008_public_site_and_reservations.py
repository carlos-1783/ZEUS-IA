"""Add public site (slug/enabled) on users and reservations table

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # User: web pública por cliente (opción B para todos)
    op.add_column("users", sa.Column("public_site_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("public_site_slug", sa.String(100), nullable=True, index=True))
    op.create_index("ix_users_public_site_slug_unique", "users", ["public_site_slug"], unique=True)

    # Reservas: multi-tenant por user_id (dueño del negocio)
    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("guest_name", sa.String(200), nullable=False),
        sa.Column("guest_phone", sa.String(50), nullable=False),
        sa.Column("guest_email", sa.String(255), nullable=True),
        sa.Column("reservation_date", sa.Date(), nullable=False, index=True),
        sa.Column("reservation_time", sa.String(20), nullable=False),
        sa.Column("num_guests", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("table_id", sa.String(50), nullable=True),
        sa.Column("table_name", sa.String(100), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="web"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("reservations")
    op.drop_index("ix_users_public_site_slug_unique", table_name="users")
    op.drop_column("users", "public_site_slug")
    op.drop_column("users", "public_site_enabled")
