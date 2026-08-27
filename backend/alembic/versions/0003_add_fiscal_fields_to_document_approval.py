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
    # document_approvals nunca tuvo una migración que la creara — dependía
    # por completo de Base.metadata.create_all() (app/db/base.py), igual
    # que el resto de tablas documentadas en el Bloque 2 (ver
    # alembic/versions/0043_agent_activities_company_id.py y
    # AUDIT_FIX_BLOQUE2.md). Detectado ejecutando `alembic upgrade head`
    # desde cero contra un PostgreSQL real: rompía aquí con
    # "relation document_approvals does not exist" — la propia migración
    # 0015 ya admitía el síntoma en su docstring sin arreglar la causa
    # (solo hacía no-op si la tabla no existía). Se crea aquí, con el
    # esquema base tal como existía en este punto de la historia (antes de
    # que 0015/0016/0025 añadieran sus columnas propias).
    bind = op.get_bind()
    if 'document_approvals' not in sa.inspect(bind).get_table_names():
        op.create_table(
            'document_approvals',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('agent_name', sa.String(length=50), nullable=False),
            sa.Column('document_type', sa.String(length=100), nullable=False),
            sa.Column('document_payload_json', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
            sa.Column('advisor_email', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_document_approvals_id'), 'document_approvals', ['id'], unique=False)
        op.create_index(op.f('ix_document_approvals_user_id'), 'document_approvals', ['user_id'], unique=False)
        op.create_index(op.f('ix_document_approvals_agent_name'), 'document_approvals', ['agent_name'], unique=False)
        op.create_index(op.f('ix_document_approvals_status'), 'document_approvals', ['status'], unique=False)

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
