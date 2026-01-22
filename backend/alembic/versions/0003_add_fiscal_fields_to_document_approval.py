"""Add fiscal fields to document_approval

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-27 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agregar campos fiscales a document_approvals
    op.add_column('document_approvals', sa.Column('ticket_id', sa.String(length=100), nullable=True))
    op.add_column('document_approvals', sa.Column('fiscal_document_type', sa.String(length=50), nullable=True))
    op.add_column('document_approvals', sa.Column('export_format', sa.String(length=20), nullable=True))
    op.add_column('document_approvals', sa.Column('exported_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('document_approvals', sa.Column('filed_external_at', sa.DateTime(timezone=True), nullable=True))
    
    # Crear índices
    op.create_index(op.f('ix_document_approvals_ticket_id'), 'document_approvals', ['ticket_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_document_approvals_ticket_id'), table_name='document_approvals')
    op.drop_column('document_approvals', 'filed_external_at')
    op.drop_column('document_approvals', 'exported_at')
    op.drop_column('document_approvals', 'export_format')
    op.drop_column('document_approvals', 'fiscal_document_type')
    op.drop_column('document_approvals', 'ticket_id')
