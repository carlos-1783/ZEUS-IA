"""ZEUS_TPV_FULL_FISCAL_INFRASTRUCTURE_ES_003: tax_rates, fiscal_profiles, tpv_sales, tpv_sale_items

Revision ID: 0004
Revises: 0003
Create Date: 2026-01-23

"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # tax_rates: múltiples IVAs por empresa/usuario
    op.create_table('tax_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('rate', sa.Numeric(5, 4), nullable=False),  # e.g. 0.2100 = 21%
        sa.Column('applies_to', sa.String(length=20), nullable=False),  # product, service, takeaway, onsite
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tax_rates_user_id'), 'tax_rates', ['user_id'], unique=False)
    op.create_index(op.f('ix_tax_rates_applies_to'), 'tax_rates', ['applies_to'], unique=False)

    # fiscal_profiles: régimen IVA y recargo equivalencia
    op.create_table('fiscal_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('vat_regime', sa.String(length=30), nullable=False),  # general, recargo_equivalencia, exento
        sa.Column('apply_recargo_equivalencia', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('recargo_rate', sa.Numeric(5, 4), nullable=True),  # e.g. 0.0520 = 5.2%
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fiscal_profiles_user_id'), 'fiscal_profiles', ['user_id'], unique=False)

    # tpv_sales: cabecera de venta TPV (snapshot fiscal inmutable)
    op.create_table('tpv_sales',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.String(length=100), nullable=False),
        sa.Column('document_type', sa.String(length=20), nullable=False),  # ticket, factura
        sa.Column('sale_date', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('payment_method', sa.String(length=30), nullable=False),
        sa.Column('consumption_type', sa.String(length=20), nullable=True),  # onsite, takeaway
        sa.Column('subtotal', sa.Numeric(12, 2), nullable=False),
        sa.Column('tax_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('recargo_amount', sa.Numeric(12, 2), nullable=True, server_default=sa.text('0')),
        sa.Column('total', sa.Numeric(12, 2), nullable=False),
        sa.Column('customer_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tpv_sales_user_id'), 'tpv_sales', ['user_id'], unique=False)
    op.create_index(op.f('ix_tpv_sales_ticket_id'), 'tpv_sales', ['ticket_id'], unique=True)
    op.create_index(op.f('ix_tpv_sales_sale_date'), 'tpv_sales', ['sale_date'], unique=False)

    # tpv_sale_items: líneas con snapshot fiscal por línea (inmutable)
    op.create_table('tpv_sale_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tpv_sale_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.String(length=100), nullable=False),
        sa.Column('product_name', sa.String(length=200), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 2), nullable=False),
        sa.Column('unit_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('tax_rate_snapshot', sa.Numeric(5, 4), nullable=False),
        sa.Column('tax_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('base_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('recargo_rate_snapshot', sa.Numeric(5, 4), nullable=True),
        sa.Column('recargo_amount', sa.Numeric(12, 2), nullable=True, server_default=sa.text('0')),
        sa.Column('consumption_type', sa.String(length=20), nullable=True),  # onsite, takeaway
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['tpv_sale_id'], ['tpv_sales.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tpv_sale_items_tpv_sale_id'), 'tpv_sale_items', ['tpv_sale_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tpv_sale_items_tpv_sale_id'), table_name='tpv_sale_items')
    op.drop_table('tpv_sale_items')
    op.drop_index(op.f('ix_tpv_sales_sale_date'), table_name='tpv_sales')
    op.drop_index(op.f('ix_tpv_sales_ticket_id'), table_name='tpv_sales')
    op.drop_index(op.f('ix_tpv_sales_user_id'), table_name='tpv_sales')
    op.drop_table('tpv_sales')
    op.drop_index(op.f('ix_fiscal_profiles_user_id'), table_name='fiscal_profiles')
    op.drop_table('fiscal_profiles')
    op.drop_index(op.f('ix_tax_rates_applies_to'), table_name='tax_rates')
    op.drop_index(op.f('ix_tax_rates_user_id'), table_name='tax_rates')
    op.drop_table('tax_rates')
