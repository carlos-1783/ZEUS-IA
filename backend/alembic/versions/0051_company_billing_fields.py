"""company_billing_fields — CIF/NIF, razón social e IBAN cifrado para onboarding

Revision ID: 0051
Revises: 0050

Nota de consolidación (feature/consolidacion-final): renumerada de "0045" a
"0051" al fusionar — colisionaba con "0045_fix_misleading_company_id_naming.py"
(ya mergeado). Encadenada tras "0050", sin cambios de lógica.
"""
from alembic import op
import sqlalchemy as sa

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("companies")}

    if "tax_id" not in cols:
        op.add_column("companies", sa.Column("tax_id", sa.String(20), nullable=True))
        op.create_index("ix_companies_tax_id", "companies", ["tax_id"])
    if "legal_name" not in cols:
        op.add_column("companies", sa.Column("legal_name", sa.String(255), nullable=True))
    if "iban_encrypted" not in cols:
        op.add_column("companies", sa.Column("iban_encrypted", sa.Text(), nullable=True))


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns("companies")}

    if "iban_encrypted" in cols:
        op.drop_column("companies", "iban_encrypted")
    if "legal_name" in cols:
        op.drop_column("companies", "legal_name")
    if "tax_id" in cols:
        op.drop_index("ix_companies_tax_id", table_name="companies")
        op.drop_column("companies", "tax_id")
