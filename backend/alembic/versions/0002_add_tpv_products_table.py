"""Add TPV Products table

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tpv_products table with multi-tenancy support
    op.create_table('tpv_products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('price', sa.Float(precision=2), nullable=False),
        sa.Column('price_with_iva', sa.Float(precision=2), nullable=False),
        sa.Column('iva_rate', sa.Float(precision=4), nullable=True),
        sa.Column('stock', sa.Integer(), nullable=True),
        sa.Column('image', sa.String(length=500), nullable=True),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tpv_products_id'), 'tpv_products', ['id'], unique=False)
    op.create_index(op.f('ix_tpv_products_user_id'), 'tpv_products', ['user_id'], unique=False)
    op.create_index(op.f('ix_tpv_products_product_id'), 'tpv_products', ['product_id'], unique=False)
    op.create_index(op.f('ix_tpv_products_category'), 'tpv_products', ['category'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tpv_products_category'), table_name='tpv_products')
    op.drop_index(op.f('ix_tpv_products_product_id'), table_name='tpv_products')
    op.drop_index(op.f('ix_tpv_products_user_id'), table_name='tpv_products')
    op.drop_index(op.f('ix_tpv_products_id'), table_name='tpv_products')
    op.drop_table('tpv_products')
