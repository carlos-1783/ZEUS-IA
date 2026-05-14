"""CRM oficina: clientes multi-empresa, expedientes, actividad, vínculo cobros tpv_sales

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-12

"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_customers_email", table_name="customers")
    op.create_index(op.f("ix_customers_email"), "customers", ["email"], unique=False)

    op.add_column(
        "customers",
        sa.Column("company_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_customers_company_id",
        "customers",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_customers_owner_user_id",
        "customers",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_customers_company_id"), "customers", ["company_id"], unique=False)

    op.create_table(
        "customer_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_customer_records_company_id", "customer_records", ["company_id"])
    op.create_index("ix_customer_records_customer_id", "customer_records", ["customer_id"])

    op.create_table(
        "crm_activity_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "customer_record_id",
            sa.Integer(),
            sa.ForeignKey("customer_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("summary", sa.String(512), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_crm_activity_logs_company_id", "crm_activity_logs", ["company_id"])
    op.create_index("ix_crm_activity_logs_customer_id", "crm_activity_logs", ["customer_id"])

    op.create_table(
        "crm_sale_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "customer_record_id",
            sa.Integer(),
            sa.ForeignKey("customer_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tpv_sale_id", sa.Integer(), sa.ForeignKey("tpv_sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_crm_sale_links_record_id", "crm_sale_links", ["customer_record_id"])
    op.create_index("ix_crm_sale_links_tpv_sale_id", "crm_sale_links", ["tpv_sale_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_crm_sale_links_tpv_sale_id", table_name="crm_sale_links")
    op.drop_index("ix_crm_sale_links_record_id", table_name="crm_sale_links")
    op.drop_table("crm_sale_links")

    op.drop_index("ix_crm_activity_logs_customer_id", table_name="crm_activity_logs")
    op.drop_index("ix_crm_activity_logs_company_id", table_name="crm_activity_logs")
    op.drop_table("crm_activity_logs")

    op.drop_index("ix_customer_records_customer_id", table_name="customer_records")
    op.drop_index("ix_customer_records_company_id", table_name="customer_records")
    op.drop_table("customer_records")

    op.drop_constraint("fk_customers_owner_user_id", "customers", type_="foreignkey")
    op.drop_constraint("fk_customers_company_id", "customers", type_="foreignkey")
    op.drop_index(op.f("ix_customers_company_id"), table_name="customers")
    op.drop_column("customers", "owner_user_id")
    op.drop_column("customers", "company_id")

    op.drop_index(op.f("ix_customers_email"), table_name="customers")
    op.create_index(op.f("ix_customers_email"), "customers", ["email"], unique=True)
