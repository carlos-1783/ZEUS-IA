"""company_type para segmentación de módulos por tipo de negocio."""

from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

COMPANY_TYPE_ENUM = ("bar_restaurant", "office")


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("company_type", sa.String(32), nullable=True),
    )
    op.create_index("ix_companies_company_type", "companies", ["company_type"])

    # Backfill desde metadata.business_type
    op.execute(
        """
        UPDATE companies
        SET company_type = CASE
            WHEN COALESCE(metadata->>'business_type', '') IN ('services') THEN 'office'
            WHEN COALESCE(metadata->>'business_type', '') IN ('restaurant', 'retail') THEN 'bar_restaurant'
            WHEN LOWER(COALESCE(sector, '')) LIKE '%servicio%' THEN 'office'
            WHEN LOWER(COALESCE(sector, '')) LIKE '%oficina%' THEN 'office'
            ELSE 'bar_restaurant'
        END
        WHERE company_type IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_companies_company_type", table_name="companies")
    op.drop_column("companies", "company_type")
