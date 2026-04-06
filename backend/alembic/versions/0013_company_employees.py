"""company_employees: empleados reales por empresa

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-06

"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_employees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role_title", sa.String(100), nullable=True),
        sa.Column("employee_code", sa.String(80), nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "employee_code", name="uq_company_employees_company_code"),
    )
    op.create_index(op.f("ix_company_employees_id"), "company_employees", ["id"], unique=False)
    op.create_index(op.f("ix_company_employees_company_id"), "company_employees", ["company_id"], unique=False)
    op.create_index(op.f("ix_company_employees_user_id"), "company_employees", ["user_id"], unique=False)
    op.create_index(op.f("ix_company_employees_employee_code"), "company_employees", ["employee_code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_company_employees_employee_code"), table_name="company_employees")
    op.drop_index(op.f("ix_company_employees_user_id"), table_name="company_employees")
    op.drop_index(op.f("ix_company_employees_company_id"), table_name="company_employees")
    op.drop_index(op.f("ix_company_employees_id"), table_name="company_employees")
    op.drop_table("company_employees")
